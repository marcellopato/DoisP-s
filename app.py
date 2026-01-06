import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import datetime
import google.generativeai as genai
import json

# --- CONFIGURAÇÃO DA MARCA DOIS PÉS ---
st.set_page_config(page_title="DoisPés", layout="centered", page_icon="🦶")

# --- CONEXÃO SEGURA COM A NUVEM (SEGREDOS) ---
try:
    if "FIREBASE_KEY" in st.secrets and "GEMINI_KEY" in st.secrets:
        # Configura a IA
        genai.configure(api_key=st.secrets["GEMINI_KEY"])
        
        # Configura o Banco
        if not firebase_admin._apps:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
    else:
        raise Exception("Chaves não encontradas")
except Exception:
    st.warning("⚠️ Configuração pendente.")
    st.info("No Streamlit Cloud, vá em Settings > Secrets e adicione suas chaves.")
    st.stop()


# --- FUNÇÕES AUXILIARES ---









def format_currency(value):
    """Formata valor float para moeda BRL (R$ 1.000,00)"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def register_user(email, password, family_code):
    try:
        user = auth.create_user(email=email, password=password)
        # Cria profile inicial
        db.collection('users').document(user.uid).set({
            'email': email,
            'family_id': family_code.upper().strip(),
            'setup_completed': False  # Flag para ativar o Wizard
        })
        st.success("✅ Conta criada! Faça login para continuar.")
    except Exception as e:
        st.error(f"Erro ao criar conta: {e}")

def login_user(email):
    # ATENÇÃO: Autenticação simplificada para protótipo. 
    try:
        user = auth.get_user_by_email(email)
        doc = db.collection('users').document(user.uid).get()
        
        if doc.exists:
            data = doc.to_dict()
            st.session_state.user_id = user.uid
            st.session_state.email = user.email
            st.session_state.family_id = data.get('family_id')
            st.session_state.setup_completed = data.get('setup_completed', False)
            st.rerun()
        else:
            st.error("Usuário sem registro no banco.")
    except Exception as e:
        st.error(f"Erro no login: {e}")

def save_wizard_data(data):
    uid = st.session_state.user_id
    batch = db.batch()
    
    # 1. Update User Profile
    user_ref = db.collection('users').document(uid)
    batch.update(user_ref, {
        'income': data['income'],
        'initial_balance': data['initial_balance'],
        'setup_completed': True
    })
    
    # 2. Add Fixed Expenses
    for item in data['fixed_expenses']:
        ref = db.collection('recurring_expenses').document()
        item['family_id'] = st.session_state.family_id
        item['user_id'] = uid
        batch.set(ref, item)
        
    # 3. Add Debts
    for item in data['debts']:
        ref = db.collection('debts').document()
        item['family_id'] = st.session_state.family_id
        item['user_id'] = uid
        batch.set(ref, item)
        
    # 4. Add Initial Balance Transaction
    if data['initial_balance'] > 0:
        trans_ref = db.collection('transactions').document()
        batch.set(trans_ref, {
            'family_id': st.session_state.family_id,
            'user_name': st.session_state.email.split('@')[0],
            'type': 'Receita',
            'value': float(data['initial_balance']),
            'description': 'Saldo Inicial (Importado)',
            'category': 'Saldo Inicial',
            'date': datetime.now()
        })

    batch.commit()
    st.session_state.setup_completed = True
    st.rerun()

# --- WIZARD COMPONENTS ---

def wizard_flow():
    st.title("🚀 Configuração Inicial")
    st.progress(st.session_state.get('wizard_step', 1) / 5)
    
    step = st.session_state.get('wizard_step', 1)
    
    # Inicializa storage do wizard
    if 'wizard_data' not in st.session_state:
        st.session_state.wizard_data = {
            'fixed_expenses': [],
            'debts': []
        }

    # --- PASSO 1: RENDA ---
    if step == 1:
        st.subheader("1. Vamos falar de dinheiro")
        with st.form("step1"):
            income = st.number_input("Quanto é a SUA renda mensal líquida?", min_value=0.0, step=100.0, format="%.2f")
            initial_balance = st.number_input("Qual seu saldo TOTAL hoje (contas + bolso)?", min_value=0.0, step=50.0, format="%.2f")
            
            if st.form_submit_button("Próximo ➡️"):
                st.session_state.wizard_data['income'] = income
                st.session_state.wizard_data['initial_balance'] = initial_balance
                st.session_state.wizard_step = 2
                st.rerun()

    # --- PASSO 2: CONTAS FIXAS ---
    elif step == 2:
        st.subheader("2. Contas Fixas (Obrigatórias)")
        st.caption("Adicione contas como Aluguel, Luz, Internet, Netflix.")
        
        # Editor de dados para listas
        if 'df_fixed' not in st.session_state:
            st.session_state.df_fixed = pd.DataFrame(columns=["Descrição", "Valor", "Dia Vencimento"])

        edited_df = st.data_editor(
            st.session_state.df_fixed, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Valor": st.column_config.NumberColumn(
                    "Valor (R$)",
                    help="Valor mensal da conta",
                    min_value=0,
                    step=0.01,
                    format="R$ %.2f"
                ),
                "Dia Vencimento": st.column_config.NumberColumn(
                    "Vencimento",
                    min_value=1,
                    max_value=31,
                    step=1,
                    format="%d"
                )
            }
        )
        
        col1, col2 = st.columns([1, 3])
        if col1.button("⬅️ Voltar"):
            st.session_state.wizard_step = 1
            st.rerun()
        if col2.button("Próximo ➡️", type="primary"):
            # Converte e salva
            fixed_list = []
            for _, row in edited_df.iterrows():
                if row["Descrição"] and row["Valor"] > 0:
                    fixed_list.append({
                        "description": row["Descrição"],
                        "amount": float(row["Valor"]),
                        "due_day": int(row["Dia Vencimento"]) if pd.notnull(row["Dia Vencimento"]) else 1
                    })
            st.session_state.wizard_data['fixed_expenses'] = fixed_list
            st.session_state.df_fixed = edited_df # Persiste estado visual
            st.session_state.wizard_step = 3
            st.rerun()

    # --- PASSO 3: DÍVIDAS ---
    elif step == 3:
        st.subheader("3. Dívidas e Empréstimos")
        st.caption("Liste parcelas de carro, empréstimos ou dívidas com terceiros.")
        
        if 'df_debts' not in st.session_state:
            st.session_state.df_debts = pd.DataFrame(columns=["Descrição", "Valor Total", "Parcelas Restantes", "Valor Parcela"])

        edited_debts = st.data_editor(
            st.session_state.df_debts, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor Parcela": st.column_config.NumberColumn(format="R$ %.2f"),
                "Parcelas Restantes": st.column_config.NumberColumn(format="%d")
            }
        )
        
        col1, col2 = st.columns([1, 3])
        if col1.button("⬅️ Voltar"):
            st.session_state.wizard_step = 2
            st.rerun()
        if col2.button("Próximo ➡️", type="primary"):
            debts_list = []
            for _, row in edited_debts.iterrows():
                if row["Descrição"]:
                    debts_list.append({
                        "description": row["Descrição"],
                        "total_value": float(row["Valor Total"] or 0),
                        "remaining_installments": int(row["Parcelas Restantes"] or 0),
                        "installment_value": float(row["Valor Parcela"] or 0)
                    })
            st.session_state.wizard_data['debts'] = debts_list
            st.session_state.df_debts = edited_debts
            st.session_state.wizard_step = 4
            st.rerun()

    # --- PASSO 4: EXTRAS ---
    elif step == 4:
        st.subheader("4. Detalhes Finais")
        with st.form("step4"):
            credit_limit = st.number_input("Limite TOTAL do Cartão de Crédito", step=100.0, format="%.2f")
            current_invoice = st.number_input("Valor da Fatura Atual", step=50.0, format="%.2f")
            goals = st.text_area("Quais suas metas financeiras? (Ex: Comprar casa, Viajar)", height=100)
            
            if st.form_submit_button("Finalizar Configuração 🎉"):
                st.session_state.wizard_data['credit_card'] = {
                    'limit': credit_limit,
                    'current_invoice': current_invoice
                }
                st.session_state.wizard_data['goals'] = goals
                save_wizard_data(st.session_state.wizard_data)

# --- DASHBOARD (CÓDIGO EXISTENTE REFATORADO) ---
def main_dashboard():
    # Sidebar
    with st.sidebar:
        st.header("DoisPés 🦶")
        st.write(f"Usuário: **{st.session_state.email}**")
        st.info(f"Família: {st.session_state.family_id}")
        


        st.divider()
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    # --- ÁREA PRINCIPAL ---
    st.title(f"Olá, {st.session_state.email.split('@')[0]}!")
    


    # --- 1. ADICIONAR ---
    # --- 1. ADICIONAR ---
    with st.expander("💸 Novo Lançamento", expanded=True):
        # AI Upload Section
        if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
        uploaded_file = st.file_uploader("📸 Foto da Conta ou Recibo (IA)", type=["jpg", "png", "jpeg", "webp", "pdf"], key=f"uploader_{st.session_state.uploader_key}")
        
        # Initialize form state if not present
        if 'new_launch_val' not in st.session_state: st.session_state.new_launch_val = 0.0
        if 'new_launch_desc' not in st.session_state: st.session_state.new_launch_desc = ""
        if 'new_launch_cat' not in st.session_state: st.session_state.new_launch_cat = "Outros"
        if 'new_launch_type' not in st.session_state: st.session_state.new_launch_type = "Despesa"

        if uploaded_file:
            # Check if this file was already analyzed to avoid re-running on every interaction
            # We use the key to track uniqueness combined with filename
            current_file_id = f"{st.session_state.uploader_key}_{uploaded_file.name}"
            
            if 'last_analyzed_file' not in st.session_state or st.session_state.last_analyzed_file != current_file_id:
                with st.spinner("🤖 A IA está lendo seu comprovante..."):
                    try:
                        import PIL.Image
                        
                        if uploaded_file.type == "application/pdf":
                            st.warning("⚠️ Suporte a PDF em breve! Por favor use imagem (JPG/PNG).")
                        else:
                            img = PIL.Image.open(uploaded_file)
                            st.image(img, caption='Comprovante', width=200)
                            
                            # Gemini Call
                            model = genai.GenerativeModel('gemini-2.0-flash')
                            prompt = """
                            Analise esta imagem de comprovante/recibo financeiro e extraia um JSON:
                            {
                                "value": float (valor total, use ponto para decimais),
                                "description": string (nome do estabelecimento ou resumo curto),
                                "category": string (escolha uma: Casa, Mercado, Lazer, Transporte, Salário, Investimento, Outros),
                                "type": string (escolha uma: Despesa, Receita, Investimento),
                                "date": string (formato YYYY-MM-DD)
                            }
                            Se não encontrar algo, deixe null. Responda APENAS o JSON.
                            """
                            response = model.generate_content([prompt, img])
                            
                            # Clean json
                            text = response.text.replace("```json", "").replace("```", "").strip()
                            data_ai = json.loads(text)
                            
                            if data_ai:
                                st.session_state.new_launch_val = float(data_ai.get('value', 0.0) or 0.0)
                                st.session_state.new_launch_desc = data_ai.get('description', "") or ""
                                
                                category = data_ai.get('category')
                                if category in ["Casa", "Mercado", "Lazer", "Transporte", "Salário", "Investimento", "Outros"]:
                                    st.session_state.new_launch_cat = category
                                
                                type_ = data_ai.get('type')
                                if type_ in ["Despesa", "Receita", "Investimento"]:
                                    st.session_state.new_launch_type = type_
                                
                                st.session_state.last_analyzed_file = current_file_id
                                st.success("✅ Dados extraídos! Confira abaixo.")
                                st.rerun() # Rerun to update widgets with new session state values

                    except Exception as e:
                        st.error(f"Erro na leitura da IA: {e}")

        col1, col2 = st.columns(2)
        
        # Widgets linked to session_state keys
        tipo = col1.selectbox("Tipo", ["Despesa", "Receita", "Investimento"], key="new_launch_type")
        valor = col2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key="new_launch_val")
        
        col3, col4 = st.columns(2)
        desc = col3.text_input("Descrição", key="new_launch_desc")
        cat = col4.selectbox("Categoria", ["Casa", "Mercado", "Lazer", "Transporte", "Salário", "Investimento", "Outros"], key="new_launch_cat")
        
        def save_transaction():
            db.collection('transactions').add({
                'family_id': st.session_state.family_id,
                'user_name': st.session_state.email.split('@')[0],
                'type': st.session_state.new_launch_type,
                'value': float(st.session_state.new_launch_val),
                'description': st.session_state.new_launch_desc,
                'category': st.session_state.new_launch_cat,
                'date': datetime.combine(datetime.now(), datetime.min.time())
            })
            
            # Reset form safely in callback
            st.session_state.new_launch_val = 0.0
            st.session_state.new_launch_desc = ""
            if 'last_analyzed_file' in st.session_state:
                del st.session_state.last_analyzed_file
            
            # Increment uploader key to wipe the file uploader widget
            st.session_state.uploader_key += 1
            
            st.toast("Salvo!")

        st.button("Salvar Lançamento", use_container_width=True, on_click=save_transaction)

    # --- 2. DADOS ---
    # Logica de busca de dados
    docs = db.collection('transactions').where("family_id", "==", st.session_state.family_id).stream()
    data = [doc.to_dict() for doc in docs]
    
    if data:
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=False)
        
        rec = df[df['type']=='Receita']['value'].sum()
        desp = df[df['type']=='Despesa']['value'].sum()
        inv = df[df['type']=='Investimento']['value'].sum()
        saldo = rec - desp - inv
        
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Entradas", format_currency(rec))
        c2.metric("Saídas", format_currency(desp), delta=format_currency(-desp), delta_color="inverse")
        c3.metric("Saldo", format_currency(saldo), delta_color="normal" if saldo > 0 else "inverse")
        
        # Botão IA
        if st.button("✨ Pedir análise ao Consultor IA"):
            # Resgata profile do usuário para contexto extra
            user_profile = db.collection('users').document(st.session_state.user_id).get().to_dict()
            profile_txt = f"Renda: {user_profile.get('income', 0)}. Metas: {user_profile.get('goals', '')}"
            
            info_ia = f"Perfil: {profile_txt}. Dados Reais (já em reais): Receitas: {rec}, Despesas: {desp}, Saldo: {saldo}."
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            try:
                with st.spinner("Analisando..."):
                    response = model.generate_content(f"Analise financeiramente: {info_ia}")
                    st.info(response.text)
            except Exception as e:
                st.error(f"Erro na IA: {e}")

        # Gráficos
        tab1, tab2 = st.tabs(["Gráficos", "Extrato"])
        with tab1:
            if not df[df['type']=='Despesa'].empty:
                st.plotly_chart(px.pie(df[df['type']=='Despesa'], values='value', names='category', hole=0.4), use_container_width=True)
        with tab2:
            st.dataframe(
                df[['date', 'description', 'value', 'type']], 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "description": "Descrição",
                    "value": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "type": "Tipo"
                }
            )

# --- CONTROLLER PRINCIPAL ---

if 'user_id' not in st.session_state:
    # TELA DE LOGIN
    st.title("🦶🦶 DoisPés")
    tab1, tab2 = st.tabs(["Entrar", "Nova Conta"])
    with tab1:
        email = st.text_input("Email")
        if st.button("Entrar"):
            login_user(email)
    with tab2:
        n_email = st.text_input("Novo Email")
        n_pass = st.text_input("Nova Senha", type="password")
        code = st.text_input("Código da Família")
        if st.button("Cadastrar"):
            register_user(n_email, n_pass, code)

elif not st.session_state.get('setup_completed', False):
    # TELA DE WIZARD
    wizard_flow()

else:
    # TELA PRINCIPAL
    main_dashboard()
