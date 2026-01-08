# <img src="dois-pes.png" alt="DoisPés Logo" width="100" style="vertical-align: middle;"> DoisPés


**Finanças a dois, futuro de milhões.**

O **DoisPés** é um aplicativo simples e poderoso para casais gerenciarem suas finanças juntos. Ele utiliza o Google Firebase para sincronização em tempo real e IA (Google Gemini) para dar conselhos financeiros personalizados.

## ✨ Funcionalidades

*   **⚡ Setup Mágico (Wizard):** Um passo-a-passo inicial para cadastrar Renda, Saldo, Contas Fixas, Dívidas e Metas.
*   **🏡 Contas Compartilhadas:** Tudo é vinculado pelo "Código da Família". O casal vê a mesma carteira.
*   **📊 Dashboard Completo:** Acompanhe Entradas, Saídas e Saldo com gráficos interativos.
*   **🤖 Consultor IA:** Um botão mágico que analisa sua situação financeira atual, metas e perfil, dando dicas práticas.
*   **📱 Mobile First:** Layout pensado para uso no celular.

## 🛠️ Tecnologias

*   **Frontend:** [Streamlit](https://streamlit.io/) (Python)
*   **Backend:** Google Firestore (Firebase)
*   **Auth:** Firebase Authentication
*   **IA:** Google Gemini 1.5 Flash

## 🚀 Como Rodar Localmente

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/seu-usuario/doispes.git
    cd doispes
    ```

2.  **Crie um ambiente virtual e instale as dependências:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure os Segredos:**
    Crie um arquivo `.streamlit/secrets.toml` na raiz do projeto e adicione suas chaves do Firebase e Gemini:
    ```toml
    GEMINI_KEY = "SUA_CHAVE_AQUI"
    FIREBASE_KEY = '{"type": "service_account", ...}' 
    ```

4.  **Execute o App:**
    ```bash
    streamlit run app.py
    ```

## 📝 Próximos Passos

- [ ] Adicionar edição de lançamentos.
- [ ] Implementar categorias personalizadas.
- [ ] Criar relatórios em PDF.
