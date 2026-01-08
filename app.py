import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import datetime
import google.generativeai as genai
import json
import re
import requests
import utils.importers as importers

# --- CONFIGURAÇÃO DA MARCA DOIS PÉS ---
st.set_page_config(page_title="DoisPés", page_icon="dois-pes.png", layout="wide")

# --- MOBILE PWA CONFIG ---
st.markdown("""
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0E1117">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
""", unsafe_allow_html=True)

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

def validate_password(password):
    """Valida força da senha: mínimo 8 caracteres, letras e números"""
    if len(password) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    if not re.search(r"[a-zA-Z]", password):
        return False, "Senha deve conter letras"
    if not re.search(r"[0-9]", password):
        return False, "Senha deve conter números"
    return True, "Senha válida"

def register_user(email, password, family_code):
    """Registra novo usuário com validação de senha"""
    # Validar senha
    is_valid, message = validate_password(password)
    if not is_valid:
        st.error(f"❌ {message}")
        return
    
    # Validar family_code
    if not family_code or len(family_code.strip()) < 3:
        st.error("❌ Código da família deve ter no mínimo 3 caracteres")
        return
    
    try:
        # Criar usuário no Firebase Auth
        user = auth.create_user(email=email, password=password)
        
        # Criar profile inicial no Firestore
        db.collection('users').document(user.uid).set({
            'email': email,
            'family_id': family_code.upper().strip(),
            'setup_completed': False,
            'created_at': datetime.now()
        })
        
        st.success("✅ Conta criada! Faça login para continuar.")
    except Exception as e:
        error_msg = str(e)
        if "EMAIL_EXISTS" in error_msg or "already exists" in error_msg:
            st.error("❌ Este email já está cadastrado")
        else:
            st.error(f"❌ Erro ao criar conta: {error_msg}")

def login_user(email, password):
    """Login seguro com verificação de senha via Firebase REST API"""
    try:
        # Firebase REST API para verificar credenciais
        # Nota: Firebase Admin SDK não verifica senha, precisamos usar REST API
        api_key = st.secrets.get("FIREBASE_API_KEY")
        
        if not api_key:
            st.error("⚠️ Configuração incompleta. Configure FIREBASE_API_KEY em secrets.toml")
            return
        
        # Autenticar via Firebase REST API
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', '')
            
            if "INVALID_PASSWORD" in error_msg or "INVALID_LOGIN_CREDENTIALS" in error_msg:
                st.error("❌ Email ou senha incorretos")
            elif "USER_DISABLED" in error_msg:
                st.error("❌ Conta desabilitada")
            elif "TOO_MANY_ATTEMPTS" in error_msg:
                st.error("❌ Muitas tentativas. Aguarde alguns minutos.")
            else:
                st.error(f"❌ Erro no login: {error_msg}")
            return
        
        # Login bem-sucedido, buscar dados do usuário
        auth_data = response.json()
        user_id = auth_data['localId']
        
        # Buscar profile do Firestore
        doc = db.collection('users').document(user_id).get()
        
        if doc.exists:
            data = doc.to_dict()
            
            # Validar que o usuário pertence a uma família
            if not data.get('family_id'):
                st.error("❌ Usuário sem código da família. Entre em contato com o suporte.")
                return
            
            # Salvar sessão
            st.session_state.user_id = user_id
            st.session_state.email = email
            st.session_state.family_id = data.get('family_id')
            st.session_state.user_name = data.get('display_name', email.split('@')[0])
            st.session_state.setup_completed = data.get('setup_completed', False)
            st.session_state.auth_token = auth_data.get('idToken')  # Para uso futuro
            
            st.rerun()
        else:
            st.error("❌ Usuário não encontrado no banco de dados")
            
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de conexão: {e}")
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")

def reset_password(email):
    """Envia email de recuperação de senha"""
    try:
        api_key = st.secrets.get("FIREBASE_API_KEY")
        
        if not api_key:
            st.error("⚠️ Configuração incompleta")
            return
        
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            st.success("✅ Email de recuperação enviado! Verifique sua caixa de entrada.")
        else:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', '')
            
            if "EMAIL_NOT_FOUND" in error_msg:
                st.error("❌ Email não cadastrado")
            else:
                st.error(f"❌ Erro: {error_msg}")
    except Exception as e:
        st.error(f"❌ Erro ao enviar email: {e}")

# --- AUTORIZAÇÃO E SEGURANÇA ---

def require_auth():
    """Middleware: garante que usuário está autenticado"""
    if 'user_id' not in st.session_state:
        st.error("🔒 Sessão expirada. Faça login novamente.")
        st.stop()
    return True

def check_family_access(family_id):
    """Valida se o usuário tem acesso à família especificada"""
    require_auth()
    
    user_family = st.session_state.get('family_id')
    if not user_family:
        st.error("❌ Usuário sem família associada")
        st.stop()
        return False
    
    if user_family != family_id:
        st.error("🚫 Acesso negado: você não pertence a esta família")
        st.stop()
        return False
    
    return True

def get_user_family_id():
    """Retorna family_id do usuário autenticado com validação"""
    require_auth()
    family_id = st.session_state.get('family_id')
    
    if not family_id:
        st.error("❌ Código da família não encontrado. Entre em contato com o suporte.")
        st.stop()
    
    return family_id


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
def render_debts_view():
    st.title("💳 Gestão de Dívidas")
    
    family_id = st.session_state.family_id
    loans = db.collection('debts').where('family_id', '==', family_id).stream()
    data = [d.to_dict() | {'id': d.id} for d in loans]
    
    if data:
        # --- HEADER METRICS ---
        df = pd.DataFrame(data)
        total_divida = df['total_value'].sum()
        total_parcelas_mes = df['installment_value'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Confirmado", format_currency(total_divida), help="Soma total do que falta pagar")
        c2.metric("Comprometimento Mensal", format_currency(total_parcelas_mes), help="Quanto sai do seu bolso todo mês só para dívidas")
        c3.metric("Qtd. Dívidas", len(data), help="Número de contratos ativos")
        
        st.markdown("---")

        # --- AI STRATEGIST ---
        with st.expander("🤖 Consultor de Quitação (IA)", expanded=False):
            st.write("A IA pode analisar suas dívidas e sugerir qual ordem de pagamento economiza mais juros (Método Avalanche vs Bola de Neve).")
            if st.button("Gerar Estratégia de Pagamento"):
                with st.spinner("Analisando contratos e valores..."):
                    # Prepare data for AI
                    debts_summary = "\n".join([f"- {d['description']}: R$ {d['total_value']} (Parcela R$ {d.get('installment_value',0)})" for d in data])
                    
                    prompt = f"""
                    Atue como um especialista em recuperação de crédito. Analise essa lista de dívidas pessoais:
                    {debts_summary}
                    
                    1. Identifique quais provavelmente têm os juros mais abusivos (ex: Crefisa, Cheque Especial, Cartão) e devem ser prioridade.
                    2. Sugira uma estratégia de quitação (Avalanche ou Bola de Neve) explicando o porquê.
                    3. Liste 3 perguntas que o usuário deve fazer ao credor para tentar negociar um desconto à vista.
                    
                    Seja direto e prático. Use formatação markdown.
                    """
                    
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    try:
                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Erro na análise: {e}")

        st.markdown("### 📋 Seus Contratos")
        
        # --- CARDS GRID ---
        # Sort by value descending to show biggest first
        data_sorted = sorted(data, key=lambda x: x['total_value'], reverse=True)
        
        for debt in data_sorted:
            # Determine card color/style based on severity (heuristic)
            val = debt['total_value']
            color_border = "#3498db" # Blue default
            icon = "📄"
            
            if val > 5000:
                color_border = "#e74c3c" # Red
                icon = "🚨"
            elif val > 1000:
                color_border = "#f39c12" # Orange
                icon = "⚠️"
            
            restam = debt.get('remaining_installments', 1)
            inst_val = debt.get('installment_value', 0)
            
            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background-color: #262730; 
                        padding: 15px; 
                        border-radius: 8px; 
                        border-left: 5px solid {color_border};
                        margin-bottom: 15px;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3 style="margin: 0; font-size: 18px; color: white;">{icon} {debt['description']}</h3>
                            <span style="background-color: #e74c3c; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">R$ {val:,.2f}</span>
                        </div>
                        <div style="display: flex; gap: 20px; margin-top: 10px; color: #cccccc; font-size: 14px;">
                            <span>📦 Parcela: <b>R$ {inst_val:,.2f}</b></span>
                            <span>⏳ Restam: <b>{restam}x</b></span>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Context Actions
                c_act1, c_act2 = st.columns([1, 4])
                if c_act1.button("🗑️", key=f"del_{debt['id']}", help="Excluir dívida"):
                    db.collection('debts').document(debt['id']).delete()
                    st.rerun()
                
                # Placeholder for negotiation status styling (could be a badge in future)

    else:
        st.info("Nenhuma dívida cadastrada (Amém? 🙏)")

def render_recurring_view():
    st.title("📅 Contas Fixas (Recorrentes)")
    
    family_id = st.session_state.family_id
    recs = db.collection('recurring_expenses').where('family_id', '==', family_id).stream()
    data = [r.to_dict() | {'id': r.id} for r in recs]
    
    if data:
        df = pd.DataFrame(data)
        total_monthly = df['amount'].sum()
        
        # --- METRICS ---
        c1, c2 = st.columns(2)
        c1.metric("Custo Fixo Mensal", format_currency(total_monthly), help="Total que sai todo mês")
        c2.metric("Qtd. Contas", len(data))
        
        st.markdown("---")
        
        # --- COLOR LOGIC ---
        # Palette of nice UI colors
        palette = ["#3498db", "#9b59b6", "#e67e22", "#1abc9c", "#f1c40f", "#e74c3c", "#34495e", "#2ecc71"]
        
        # Assign a distinct color from palette to each description
        colors = {}
        for i, desc in enumerate(df['description'].unique()):
            colors[desc] = palette[i % len(palette)]
            
        df['color'] = df['description'].map(colors)

        # --- CHARTS ---
        col_chart, col_list = st.columns([1, 1])
        
        with col_chart:
            st.subheader("🍰 Onde gasto meu fixo?")
            fig = px.pie(
                df, 
                values='amount', 
                names='description', 
                hole=0.4,
                color='description',
                color_discrete_map=colors
            )
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_list:
            st.subheader("🗓️ Lista de Contas")
            # Sort by Day
            df_sorted = df.sort_values('due_day')
            
            for index, row in df_sorted.iterrows():
                val = row['amount']
                
                # SEVERITY INDICATOR (Inner Badge)
                severity_icon = "🔵" # Normal
                if val > 1000: severity_icon = "🔴" # High
                elif val > 500: severity_icon = "🟠" # Medium
                
                icon = "📅"
                if val > 1000: icon = "🏠"
                
                st.markdown(
                    f"""
                    <div style="
                        background-color: #262730; 
                        padding: 10px 15px; 
                        border-radius: 8px; 
                        border-left: 5px solid {row['color']};
                        margin-bottom: 10px;
                        display: flex; justify-content: space-between; align-items: center;
                    ">
                        <div>
                            <div style="font-size: 16px; font-weight: bold; color: white;">
                                {icon} {row['description']}
                            </div>
                            <div style="font-size: 13px; color: #aaaaaa; margin-top: 2px;">
                                Vence dia {int(row['due_day'])}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 18px; color: #ecf0f1; font-weight: bold;">
                                {format_currency(row['amount'])}
                            </div>
                            <div style="font-size: 12px; margin-top: 2px;">
                                {severity_icon}
                            </div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
    else:
        st.info("Nenhuma conta recorrente cadastrada.")


def render_cards_view():
    st.title("💳 Cartões de Crédito")
    
    # Form para adicionar cartão
    with st.expander("➕ Adicionar Novo Cartão", expanded=False):
        with st.form("new_card_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Apelido do Cartão", placeholder="Ex: Nubank Roxinho")
            limit = col2.number_input("Limite Total (R$)", min_value=0.0, step=100.0)
            
            col3, col4 = st.columns(2)
            close_day = col3.number_input("Dia Fechamento", min_value=1, max_value=31, value=1)
            due_day = col4.number_input("Dia Vencimento", min_value=1, max_value=31, value=10)
            
            if st.form_submit_button("Salvar Cartão"):
                if name and limit > 0:
                    ref = db.collection('credit_cards').document()
                    ref.set({
                        'name': name,
                        'limit': limit,
                        'closing_day': int(close_day),
                        'due_day': int(due_day),
                        'family_id': st.session_state.family_id,
                        'user_id': st.session_state.user_id,
                        'created_at': datetime.now()
                    })
                    st.success(f"Cartão {name} salvo!")
                    st.rerun()
                else:
                    st.error("Preencha nome e limite.")

    # Listar cartões
    family_id = st.session_state.family_id
    cards = db.collection('credit_cards').where('family_id', '==', family_id).stream()
    data = [c.to_dict() | {'id': c.id} for c in cards] # Include ID
    
    if data:
        st.subheader("Meus Cartões")
        for card in data:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"### {card.get('name')}")
                c1.caption(f"Fecha dia {card.get('closing_day')} • Vence dia {card.get('due_day')}")
                
                # Barra de limite (Simulação por enquanto, futuramente conectar com faturas)
                limit_val = card.get('limit', 0)
                used_val = 0 # TODO: Calcular gastos reais
                
                c1.progress(0, text=f"Limite: {format_currency(limit_val)}")
                
                if c2.button("🗑️", key=f"del_{card['id']}"):
                    db.collection('credit_cards').document(card['id']).delete()
                    st.rerun()
    else:
        st.info("Nenhum cartão cadastrado. Adicione um acima! 👆")


def save_imported_data(items):
    """Salva itens importados nas coleções apropriadas"""
    batch = db.batch()
    uid = st.session_state.user_id
    family_id = st.session_state.family_id
    
    count_rec = 0
    count_debt = 0
    count_trans = 0
    
    for item in items:
        # 1. Dívidas
        if item['type'] == 'debt':
            ref = db.collection('debts').document()
            batch.set(ref, {
                'description': item['description'],
                'total_value': float(item['value']),
                'remaining_installments': int(item.get('installments_count', 1)),
                'installment_value': float(item.get('installment_value', item['value'])),
                'family_id': family_id,
                'user_id': uid,
                'created_at': datetime.now()
            })
            count_debt += 1
            
        # 2. Despesas Fixas / Recorrentes
        elif item['type'] == 'recurring':
            ref = db.collection('recurring_expenses').document()
            day = 1
            if item.get('date'):
                day = item['date'].day
            
            batch.set(ref, {
                'description': item['description'],
                'amount': float(item['value']),
                'due_day': int(day),
                'family_id': family_id,
                'user_id': uid
            })
            count_rec += 1
            
        # 3. Transações (Despesas comuns)
        else:
            ref = db.collection('transactions').document()
            date_val = datetime.now()
            if item.get('date'):
                # Converter date object para datetime
                d = item['date']
                date_val = datetime(d.year, d.month, d.day)
                
            batch.set(ref, {
                'description': item['description'],
                'value': float(item['value']),
                'type': 'Despesa',
                'category': 'Importado',
                'date': date_val,
                'family_id': family_id,
                'user_name': st.session_state.get('user_name', 'User'),
                'user_id': uid
            })
            count_trans += 1
            
    batch.commit()
    st.success(f"✅ Importação concluída! Dívidas: {count_debt}, Fixas: {count_rec}, Transações: {count_trans}")
    st.balloons()


def render_import_view():
    st.title("📥 Importar Dados")
    
    # Adicionar opção de limpar tudo para testes
    with st.expander("⚠️ Zona de Perigo"):
        if st.button("🗑️ Limpar TODO o Banco de Dados (Use com cautela)"):
            uid = st.session_state.user_id
            # Clean collections
            for coll in ['transactions', 'debts', 'recurring_expenses']:
                docs = db.collection(coll).where('user_id', '==', uid).stream()
                for doc in docs:
                    doc.reference.delete()
            st.warning("Banco limpo!")
            st.rerun()

    st.write("Importe suas contas a partir de arquivos XML ou use a IA para ler extratos.")
    
    if 'uploader_key_xml' not in st.session_state:
        st.session_state.uploader_key_xml = 0

    uploaded_file = st.file_uploader("📂 Selecione o arquivo XML (Excel 2003)", type=['xml'], key=f"xml_uploader_{st.session_state.uploader_key_xml}")
    
    if uploaded_file:
        try:
            # GARANTIR ponteiro no início
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('utf-8')
            
            result = importers.parse_excel_xml(content)
            
            if "error" in result:
                st.error(f"Erro ao ler arquivo: {result['error']}")
            else:
                items = result['items']
                st.info(f"{len(items)} itens encontrados no arquivo.")
                
                # Preview matches logic
                import pandas as pd
                df = pd.DataFrame(items)
                st.dataframe(df, use_container_width=True)
                
                if st.button("💾 Confirmar e Importar Tudo", type="primary"):
                    print(f"Iniciando importação de {len(items)} itens...")
                    save_imported_data(items)
                    # Forçar reset do uploader mudando a key
                    st.session_state.uploader_key_xml = st.session_state.get('uploader_key_xml', 0) + 1
                    st.success("✅ Importação realizada com sucesso! Vá ao Dashboard para conferir.")
                    if st.button("Ir para Dashboard"):
                        st.rerun()

        except Exception as e:
            st.error(f"Erro inesperado: {e}")
            print(f"Erro na importação: {e}")

def main_dashboard():
    # --- SIDEBAR NAVIGATION ---
    with st.sidebar:
        st.image("dois-pes.png", width=120)
        st.caption(f"Família: {st.session_state.family_id}")
        
        # Default menu
        if "menu_selection" not in st.session_state:
            st.session_state.menu_selection = "Dashboard"

        from streamlit_option_menu import option_menu
        
        menu = option_menu(
            "Menu Principal",
            ["Dashboard", "Lançamentos", "Dívidas", "Contas Fixas", "Importar Dados", "Cartões", "Perfil"],
            icons=["house", "currency-dollar", "bank", "calendar-check", "cloud-upload", "credit-card", "person"],
            menu_icon="cast",
            default_index=0,
            key="menu_selection"
        )
        
        st.divider()
        if st.button("Sair"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # --- ROUTING ---
    if menu == "Dashboard":
        render_dashboard_home()
    elif menu == "Lançamentos":
        render_launch_view()
    elif menu == "Dívidas":
        render_debts_view()
    elif menu == "Contas Fixas":
        render_recurring_view()
    elif menu == "Importar Dados":
        render_import_view()
    elif menu == "Cartões":
        render_cards_view()
    elif menu == "Perfil":
        render_profile_view()

def render_profile_view():
    st.title("👤 Meu Perfil")
    
    # User Data
    user_ref = db.collection('users').document(st.session_state.user_id)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        # Avatar Logic
        current_avatar = user_data.get('avatar_base64')
        if current_avatar:
            import base64
            from io import BytesIO
            from PIL import Image
            
            # Decode for display
            try:
                msg = base64.b64decode(current_avatar)
                buf = BytesIO(msg)
                img = Image.open(buf)
                st.image(img, width=150)
            except:
                st.error("Erro ao carregar avatar.")
                st.image("https://www.w3schools.com/howto/img_avatar.png", width=150)
        else:
            st.image("https://www.w3schools.com/howto/img_avatar.png", width=150)
            
        # Upload
        new_avatar = st.file_uploader("Trocar foto", type=['png', 'jpg', 'jpeg'])
        if new_avatar:
            if st.button("Salvar Nova Foto"):
                try:
                    from PIL import Image
                    import io
                    import base64
                    
                    image = Image.open(new_avatar)
                    
                    # Resize to optimized thumbnail
                    image.thumbnail((200, 200))
                    
                    # Convert to base64
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG", quality=80) # Compress
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    # Save to DB
                    user_ref.update({'avatar_base64': img_str})
                    st.session_state.user_avatar = img_str # Update session
                    st.success("Avatar atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar imagem: {e}")

    with col_r:
        st.subheader("Dados Pessoais")
        st.caption("ID da Família")
        st.code(st.session_state.family_id)
        
        st.caption("Email")
        st.text_input("Email", value=st.session_state.email, disabled=True)
        
        # Additional fields
        name_val = st.text_input("Nome de Exibição", value=user_data.get('name', ''), placeholder="Como você quer ser chamado?")
        income = st.number_input("Renda Mensal (R$)", value=float(user_data.get('income', 0.0)))
        goals = st.text_area("Objetivo Financeiro", value=user_data.get('goals', ''), placeholder="Ex: Comprar um carro, Aposentar cedo...")
        
        if st.button("💾 Atualizar Perfil"):
            user_ref.update({
                'name': name_val,
                'income': income,
                'goals': goals
            })
            st.session_state.user_name = name_val # Update session immediately
            st.success("Dados salvos!")

def render_launch_view():
    st.title("💸 Novo Lançamento")
    
    # Create Tabs for different launch types
    tab1, tab2 = st.tabs(["📝 Transação Simples", "💳 Nova Dívida / Parcelamento"])
    
    # --- TAB 1: SIMPLE TRANSACTION (EXISTING LOGIC) ---
    with tab1:
        # AI Upload Section
        if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
        uploaded_file = st.file_uploader("📸 Foto da Conta ou Recibo (IA)", type=["jpg", "png", "jpeg", "webp", "pdf"], key=f"uploader_{st.session_state.uploader_key}")
        
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
            
            st.toast("Transação Salva!")

        st.button("Salvar Lançamento", use_container_width=True, on_click=save_transaction)

    # --- TAB 2: REGISTER DEBT ---
    with tab2:
        st.info("Cadastre dívidas parceladas ou empréstimos de longo prazo.")
        
        d_desc = st.text_input("Credor / Descrição", placeholder="Ex: Empréstimo Itaú, Compra TV")
        
        c_d1, c_d2 = st.columns(2)
        d_total = c_d1.number_input("Valor Total Devido (R$)", min_value=0.0, step=100.0)
        d_installments = c_d2.number_input("Nº de Parcelas", min_value=1, step=1, value=12)
        
        # Auto calculate installment
        calc_installment = d_total / d_installments if d_installments > 0 else 0
        d_inst_val = st.number_input(f"Valor da Parcela (Calc: R$ {calc_installment:.2f})", value=calc_installment, min_value=0.0, step=10.0)
        
        if st.button("💾 Salvar Dívida", use_container_width=True):
            if d_desc and d_total > 0:
                db.collection('debts').add({
                    'family_id': st.session_state.family_id,
                    'user_id': st.session_state.user_id,
                    'description': d_desc,
                    'total_value': d_total,
                    'installment_value': d_inst_val,
                    'remaining_installments': d_installments,
                    'created_at': datetime.now()
                })
                st.success("Dívida cadastrada com sucesso!")
                st.toast("Dívida Salva!")
            else:
                st.error("Preencha a descrição e o valor total.")


# --- AI SERVICES ---
def get_daily_briefing(family_id, user_name, rec_expenses, debts_total, current_balance):
    """
    Gera ou recupera o briefing diário da IA.
    Chave: YYYY-MM-DD_{family_id}
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    doc_id = f"{today_str}_{family_id}"
    
    doc_ref = db.collection('daily_briefings').document(doc_id)
    doc = doc_ref.get()
    
    if doc.exists:
        return doc.to_dict()['content']
    
    # Se não existe, gerar novo
    with st.spinner("🤖 O Consultor IA está preparando seu resumo matinal..."):
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare context
        prompt = f"""
        Você é um consultor financeiro pessoal, amigável e motivador. O usuário é {user_name}.
        Data de hoje: {today_str}.
        
        PANORAMA FINANCEIRO:
        - Saldo Atual em Conta: {format_currency(current_balance)}
        - Total de Dívidas (Longo Prazo): {format_currency(debts_total)}
        - Contas Fixas Mensais: 
          {', '.join([f"{r['description']} (Dia {r['due_day']})" for r in rec_expenses[:5]])} ... e mais {max(0, len(rec_expenses)-5)} contas.
        
        OBJETIVO:
        Escreva um "Bom dia" curto e inspirador (max 3 parágrafos).
        1. Comente sobre o saldo atual (dê um alerta sutil se negativo, ou parabéns se positivo).
        2. Avise se tem alguma conta vencendo hoje ou amanhã (baseado no dia de hoje vs dia das contas fixas).
        3. Dê uma dica rápida de economia baseada no contexto de ter dívidas (se tiver) ou de investir (se tiver sobrando).
        
        Tom de voz: Otimista, "Tamo junto", parceiro. Use emojis.
        """
        
        try:
            response = model.generate_content(prompt)
            content = response.text
            
            # Save to cache
            doc_ref.set({
                'content': content,
                'created_at': datetime.now(),
                'family_id': family_id
            })
            return content
        except Exception as e:
            return f"Erro ao gerar briefing: {e}"

def render_dashboard_home():
    # --- ÁREA PRINCIPAL ---
    # Use name from session if available, else email fallback
    display_name = st.session_state.get('user_name') or st.session_state.email.split('@')[0]
    st.title(f"Olá, {display_name}!")
    
    family_id = get_user_family_id()
    
    # --- 2. DATA PROCESSING ---
    # Family Income (Sum of all members)
    # We need to find all users with the same family_id
    # Note: Using a simple query since we don't have a direct 'users' index by family_id yet, 
    # but strictly speaking we should query WHERE family_id == ...
    # For now, let's assume we can query users. If index missing, might default to current user, 
    # but let's try to do it right.
    try:
        family_users = db.collection('users').where('family_id', '==', family_id).stream()
        family_income = sum([float(u.to_dict().get('income', 0.0)) for u in family_users])
    except:
        # Fallback if index issue
        user_doc = db.collection('users').document(st.session_state.user_id).get()
        family_income = float(user_doc.to_dict().get('income', 0.0)) if user_doc.exists else 0.0
    
    # Transactions (Restore deleted block)
    docs_trans = db.collection('transactions').where("family_id", "==", family_id).stream()
    trans_data = [doc.to_dict() for doc in docs_trans]
    df_trans = pd.DataFrame(trans_data)
    
    # Debts (Installments vs Total)
    docs_debts = db.collection('debts').where("family_id", "==", family_id).stream()
    debts_data = [doc.to_dict() for doc in docs_debts]
    total_debts_liability = sum(d['total_value'] for d in debts_data)
    total_debt_monthly = sum(d.get('installment_value', 0) for d in debts_data)
    
    # Recurring (Monthly Fixed)
    docs_rec = db.collection('recurring_expenses').where("family_id", "==", family_id).stream()
    rec_data = [doc.to_dict() for doc in docs_rec]
    total_rec_monthly = sum(r['amount'] for r in rec_data)
    
    # Transactions (Variable Spend this month)
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    rec_val = 0.0 # Receitas extras
    desp_variable_val = 0.0 # Gastos variáveis
    
    if not df_trans.empty:
        df_trans['date'] = pd.to_datetime(df_trans['date'])
        # Filter current month for "Variable Spend" calculation
        df_month = df_trans[(df_trans['date'].dt.month == current_month) & (df_trans['date'].dt.year == current_year)]
        
        rec_val = df_month[df_month['type']=='Receita']['value'].sum()
        desp_variable_val = df_month[df_month['type']=='Despesa']['value'].sum()
        
        # Calculate Current Actual Balance (All time or synced bank balance)
        # For this view, let's look at "Projected Month Result"
        
    # --- CALCULO DA VISÃO CONJUNTA (DRE) ---
    total_obligations = total_rec_monthly + total_debt_monthly
    total_spent = total_obligations + desp_variable_val
    total_income = family_income + rec_val
    remaining = total_income - total_spent
    
    # --- AI MORNING BRIEFING ---
    briefing = get_daily_briefing(family_id, display_name, rec_data, total_debts_liability, remaining)
    st.info(briefing, icon="🌅")

    # --- 3. DASHBOARD UNIFICADO (VISÃO GERAL) ---
    st.markdown("### 🔭 Visão Mensal Unificada (Família)")
    
    # Waterfall Chart Data
    fig_waterfall = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = ["Renda Familiar", "Contas Fixas", "Parcelas Dívidas", "Gastos Variáveis", "SOBRA PREVISTA"],
        textposition = "outside",
        text = [f"R$ {val:.0f}" for val in [total_income, -total_rec_monthly, -total_debt_monthly, -desp_variable_val, remaining]],
        y = [total_income, -total_rec_monthly, -total_debt_monthly, -desp_variable_val, remaining],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#e74c3c"}},
        increasing = {"marker":{"color":"#2ecc71"}},
        totals = {"marker":{"color":"#3498db"}}
    ))
    fig_waterfall.update_layout(
        title="Fluxo de Caixa do Mês (DRE Pessoal)",
        showlegend = False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    st.plotly_chart(fig_waterfall, use_container_width=True)

    # --- 4. DETAILED CARDS ---
    def card(label, value, color, sub="", big=True):
        f_size = "24px" if big else "18px"
        st.markdown(
            f"""
            <div style="background-color: #1E1E1E; padding: 15px; border-radius: 10px; border-left: 5px solid {color}; height: 100%;">
                <p style="color: #AAAAAA; font-size: 12px; margin-bottom: 5px;">{label}</p>
                <p style="color: {color}; font-size: {f_size}; font-weight: bold; margin: 0;">{value}</p>
                <p style="color: #666666; font-size: 11px; margin-top: 5px;">{sub}</p>
            </div>
            """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        card("Renda Total", format_currency(total_income), "#2ecc71", "Salário + Extras")
    with c2: 
        card("Comprometido (Fixo+Dívidas)", format_currency(total_obligations), "#f39c12", f"Fixas: {format_currency(total_rec_monthly)} | Dívidas: {format_currency(total_debt_monthly)}")
    with c3:
        card("Gasto no Cartão/Pix hoje", format_currency(desp_variable_val), "#e74c3c", "Despesas Variáveis do Mês")
    with c4:
        color_res = "#3498db" if remaining > 0 else "#c0392b"
        card("Resultado Previsto", format_currency(remaining), color_res, "O que deve sobrar (ou faltar)")
    
    st.markdown("---")
    
    # --- 5. CHARTS & LISTS ---
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.subheader("📊 Visão Geral")
        tab1, tab2 = st.tabs(["Despesas do Mês", "Maiores Dívidas"])
        
        with tab1:
            if not df_trans.empty and not df_trans[df_trans['type']=='Despesa'].empty:
                st.plotly_chart(px.pie(df_trans[df_trans['type']=='Despesa'], values='value', names='category', hole=0.4), use_container_width=True)
            else:
                st.write("Sem dados de despesas este mês.")
                
        with tab2:
            if debts_data:
                df_debts = pd.DataFrame(debts_data)
                # Sort by value
                df_debts = df_debts.sort_values('total_value', ascending=False).head(5)
                st.plotly_chart(px.bar(df_debts, x='description', y='total_value', title="Top 5 Dívidas"), use_container_width=True)
            else:
                st.write("Parabéns! Nenhuma dívida ativa.")

    with col_r:
        st.subheader("📅 Próximos Vencimentos")
        # Logic to find upcoming recurring bills based on 'due_day'
        today_day = datetime.now().day
        
        # Sort recurring by proximity to today
        upcoming = []
        for r in rec_data:
            day = r['due_day']
            # Simple logic: if due day is >= today, show it. If next month, ignore for this simple view
            if day >= today_day:
                upcoming.append(r)
        
        upcoming.sort(key=lambda x: x['due_day'])
        
        if upcoming:
            for item in upcoming[:5]: # Show top 5
                with st.container(border=True):
                    st.write(f"**Dia {item['due_day']}**: {item['description']}")
                    st.caption(format_currency(item['amount']))
        else:
            st.success("Tudo pago para este mês! 🎉")

    # --- 5. EXTRATO ---
    with st.expander("📜 Extrato Detalhado", expanded=False):
        if not df_trans.empty:
            st.dataframe(
                df_trans[['date', 'description', 'value', 'type']], 
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
    c1, c2 = st.columns([1, 4])
    with c1:
        st.image("dois-pes.png", width=80)
    with c2:
        st.title("DoisPés")
        st.caption("Finanças a dois, futuro de milhões.")
    
    tab1, tab2, tab3 = st.tabs(["Entrar", "Nova Conta", "Esqueci a Senha"])
    
    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")
        
        col1, col2 = st.columns([3, 1])
        if col1.button("Entrar", type="primary", use_container_width=True):
            if email and password:
                login_user(email, password)
            else:
                st.error("❌ Preencha email e senha")
        
        if col2.button("👁️", help="Ver/ocultar senha"):
            st.info("💡 Dica: use a aba 'Esqueci a Senha' para recuperar acesso")
    
    with tab2:
        st.subheader("Criar Conta")
        n_email = st.text_input("Email", key="register_email")
        n_pass = st.text_input("Nova Senha", type="password", key="register_password")
        
        # Indicador visual de força da senha
        if n_pass:
            is_valid, msg = validate_password(n_pass)
            if is_valid:
                st.success(f"✅ {msg}")
            else:
                st.warning(f"⚠️ {msg}")
        
        st.caption("📋 Requisitos: mínimo 8 caracteres, letras e números")
        
        code = st.text_input("Código da Família", help="Escolha um código único para compartilhar com seu parceiro(a)")
        
        if st.button("Cadastrar", type="primary", use_container_width=True):
            if n_email and n_pass and code:
                register_user(n_email, n_pass, code)
            else:
                st.error("❌ Preencha todos os campos")
    
    with tab3:
        st.subheader("Recuperar Senha")
        st.info("📧 Enviaremos um link de recuperação para seu email")
        reset_email = st.text_input("Email cadastrado", key="reset_email")
        
        if st.button("Enviar Link de Recuperação", type="primary", use_container_width=True):
            if reset_email:
                reset_password(reset_email)
            else:
                st.error("❌ Digite seu email")

elif not st.session_state.get('setup_completed', False):
    # TELA DE WIZARD
    wizard_flow()

else:
    # TELA PRINCIPAL
    main_dashboard()
