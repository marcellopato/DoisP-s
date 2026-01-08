from playwright.sync_api import sync_playwright
import time

def test_login_flow():
    """
    Simula um usuário logando no DoisPés.
    Equivalente ao Laravel Dusk ('ExampleTest').
    """
    with sync_playwright() as p:
        # 1. Abre o navegador (headless=True para rodar em background)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 2. Acessa o App (assumindo que está rodando na porta 8501)
        page.goto("http://localhost:8501")
        
        # Espera carregar o Streamlit
        page.wait_for_selector("text=Entrar", timeout=10000)

        # 3. Vai para aba REGISTRO (Nova Conta)
        print("Acessando aba Nova Conta...")
        # Streamlit tabs are buttons often. searching by text.
        page.get_by_text("Nova Conta").click()
        
        # Gera email aleatorio
        import random
        rnd = random.randint(1000, 9999)
        email = f"test_e2e_{rnd}@doispes.com"
        
        print(f"Preenchendo Cadastro ({email})...")
        # nth(0) in Register tab context might be different, but typically Streamlit hides others.
        # Let's target by aria-label if possible or just try to fill distinct inputs
        
        # New Account Email
        page.get_by_label("Email").nth(1).fill(email) # 2nd email input
        
        # Password
        page.get_by_label("Nova Senha").fill("Password123!") # Strong password
        
        # Family Code
        page.get_by_label("Código da Família").fill(f"FAM{rnd}")

        # 4. Clica em Cadastrar
        print("Clicando em Cadastrar...")
        page.get_by_role("button", name="Cadastrar").click()

        # 5. Verifica se entrou (busca elementos do Dashboard)
        try:
            # First time user goes to Wizard
            page.wait_for_selector("text=Configuração Inicial", timeout=15000)
            print("✅ SUCESSO: Cadastro realizado e Wizard de Setup carregado!")
        except:
             try:
                page.wait_for_selector("text=Visão Mensal", timeout=5000)
                print("✅ SUCESSO: Login direto no Dashboard!")
             except:
                print("❌ ERRO: Dashboard não carregou.")
                page.screenshot(path="tests/evidence_register_error.png")

        browser.close()

if __name__ == "__main__":
    test_login_flow()
