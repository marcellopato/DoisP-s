import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import datetime
import google.generativeai as genai
import json

# --- CONFIGURAÇÃO DA MARCA DOIS PÉS ---
st.set_page_config(page_title="DoisPés", layout="mobile", page_icon="🦶")

# --- CONEXÃO SEGURA COM A NUVEM (SEGREDOS) ---
if "FIREBASE_KEY" in st.secrets and "GEMINI_KEY" in st.secrets:
    # 1. Configura a IA (Gemini)
    genai.configure(api_key=st.secrets["GEMINI_KEY"])
    
    # 2. Configura o Banco (Firebase)
    if not firebase_admin._apps:
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
else:
    st.warning("⚠️ Configuração pendente.")
    st.info("No Streamlit Cloud, vá em Settings > Secrets e adicione suas chaves.")
    st.stop()

# --- FUNÇÕES DO SISTEMA ---

def register_user(email, password, family_code):
    try:
        # Cria o login
        user = auth.create_user(email=email, password=password)
        # Cria o vínculo familiar no banco
        db.collection('users').document(user.uid).set({
            'email': email,
            'family_id': family_code.upper().strip()
        })
        st.success("✅ Conta criada! Acesse a aba 'Entrar'.")
    except Exception as e:
        st.error(f"Erro ao criar conta: {e}")

def login_user(email):
    # (Simplificado para uso pessoal confiável)
    try:
        user = auth.get_user_by_email(email)
        # Pega os dados da família
        doc = db.collection('users').document(user.uid).get()
        if doc.exists:
            st.session_state.user_id = user.uid
            st.session_state.email = user.email
            st.session_state.family_id = doc.to_dict()['family_id']
            st.rerun()
        else:
            st.error("Usuário sem código de família vinculado.")
    except:
        st.error("Email não encontrado.")

def add_transaction(tipo, valor, descricao, data, categoria):
    # Salva no banco compartilhado
    db.collection('transactions').add({
        'family_id': st.session_state.family_id,
        'user_name': st.session_state.email.split('@')[0], # Pega o nome antes do @
        'type': tipo,
        'value': float(valor),
        'description': descricao,
        'category': categoria,
        'date': datetime.combine(data, datetime.min.time())
    })
    st.toast("🦶 Lançamento salvo no DoisPés!")

def get_data():
    # Busca SÓ os dados da família logada
    docs = db.collection('transactions').where("family_id", "==", st.session_state.family_id).stream()
    data = [doc.to_dict() for doc in docs]
    if data:
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date', ascending=False)
    return pd.DataFrame()

def get_ai_analysis(resumo_texto):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Você é o consultor financeiro do app 'DoisPés'. Analise os dados deste casal:
    {resumo_texto}
    
    Seja breve, direto e use emojis.
    1. O casal está gastando mais do que ganha?
    2. Qual categoria está consumindo mais dinheiro?
    3. Dê uma dica curta e motivacional para eles guardarem dinheiro.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "A IA está descansando um pouco. Tente novamente."

# --- TELA DE LOGIN / CADASTRO ---
if 'user_id' not in st.session_state:
    st.title("🦶🦶 DoisPés")
    st.caption("Finanças a dois, futuro de milhões.")
    
    tab1, tab2 = st.tabs(["Entrar", "Nova Conta"])
    
    with tab1:
        email = st.text_input("Seu Email")
        if st.button("Acessar DoisPés"):
            login_user(email)
            
    with tab2:
        st.markdown("⚠️ **Importante:** Você e sua esposa devem usar o **MESMO** código abaixo.")
        new_email = st.text_input("Email para cadastro")
        new_pass = st.text_input("Senha (mín 6 dígitos)", type="password")
        code = st.text_input("Código da Família (Ex: AMOR2026)")
        
        if st.button("Criar Cadastro"):
            if len(new_pass) >= 6 and code:
                register_user(new_email, new_pass, code)
            else:
                st.warning("Senha curta ou código vazio.")

# --- TELA PRINCIPAL (LOGADO) ---
else:
    # Sidebar
    with st.sidebar:
        st.header("DoisPés 🦶")
        st.write(f"Usuário: **{st.session_state.email}**")
        st.info(f"Família: {st.session_state.family_id}")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    st.title(f"Olá, {st.session_state.email.split('@')[0]}!")
    
    # --- 1. ADICIONAR ---
    with st.expander("💸 Novo Lançamento", expanded=True):
        col1, col2 = st.columns(2)
        tipo = col1.selectbox("Tipo", ["Despesa", "Receita", "Investimento"])
        valor = col2.number_input("Valor (R$)", min_value=0.0, step=10.0)
        
        col3, col4 = st.columns(2)
        desc = col3.text_input("Descrição (Ex: Pizza, Luz)")
        cat = col4.selectbox("Categoria", ["Casa", "Mercado", "Lazer", "Transporte", "Salário", "Investimento", "Outros"])
        
        if st.button("Salvar Lançamento", use_container_width=True):
            add_transaction(tipo, valor, desc, datetime.now(), cat)
            st.rerun()
            
    # --- 2. DADOS ---
    df = get_data()
    
    if not df.empty:
        # Filtro de Mês (Opcional, pega o atual por padrão ou todos)
        df['mes'] = df['date'].dt.strftime('%Y-%m')
        mes_atual = datetime.now().strftime('%Y-%m')
        
        # Resumo Financeiro
        rec = df[df['type']=='Receita']['value'].sum()
        desp = df[df['type']=='Despesa']['value'].sum()
        inv = df[df['type']=='Investimento']['value'].sum()
        saldo = rec - desp - inv
        
        # Métricas
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Entradas", f"R$ {rec:,.2f}")
        c2.metric("Saídas", f"R$ {desp:,.2f}", delta=-desp, delta_color="inverse")
        c3.metric("Saldo", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")
        st.caption(f"Investimentos Totais: R$ {inv:,.2f}")

        # Botão Mágico da IA
        if st.button("✨ Pedir análise ao Consultor IA"):
            info_ia = f"Receitas: {rec}, Despesas: {desp}, Investimentos: {inv}. Saldo: {saldo}. Gastos recentes: {df[['description','value']].head(5).to_dict()}"
            with st.spinner("Analisando os números do casal..."):
                insight = get_ai_analysis(info_ia)
                st.info(insight)
        
        # Gráficos e Extrato
        tab_g, tab_e = st.tabs(["Gráficos", "Extrato"])
        
        with tab_g:
            if not df[df['type']=='Despesa'].empty:
                fig = px.pie(df[df['type']=='Despesa'], values='value', names='category', title='Para onde foi o dinheiro?', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            
            # Quem gastou mais?
            fig2 = px.bar(df, x='type', y='value', color='user_name', title="Quem movimentou o quê?", barmode='group')
            st.plotly_chart(fig2, use_container_width=True)

        with tab_e:
            st.dataframe(
                df[['date', 'description', 'value', 'type', 'user_name']].sort_values('date', ascending=False),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Nenhum dado encontrado. Faça o primeiro lançamento do DoisPés!")
