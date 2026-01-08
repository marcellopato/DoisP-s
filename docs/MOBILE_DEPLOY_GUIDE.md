# 📱 Guia: Transformando Streamlit em App Android (Play Store)

Sim, é totalmente possível publicar este projeto na Google Play Store sem precisar reescrever o código em outra linguagem.

A estratégia recomendada é usar **TWA (Trusted Web Activity)**.

## 🚀 O Conceito (TWA)

O TWA "empacota" seu site (que deve estar hospedado e com HTTPS, ex: Streamlit Cloud) dentro de um aplicativo Android nativo muito leve.
Ao contrário de um simples "WebView", o TWA:

- É oficial da Google e aceito na Play Store.
- Remove a barra de endereços do navegador (parece app nativo).
- Compartilha cookies com o Chrome (se o usuário já logou no Chrome, entra logado no App).

## 📋 Pré-requisitos

1. **Hospedagem**: O app DEVE estar rodando em uma URL pública com HTTPS (ex: `https://doispes.streamlit.app`).
2. **Conta de Desenvolvedor Google**: Custa $25 (pagamento único).
3. **Node.js** instalado no computador.

## 🛠️ Passo a Passo (Bubblewrap)

A ferramenta mais fácil para isso é a **Bubblewrap** (CLI oficial da Google).

### 1. Instalar o Bubblewrap

```bash
npm install -g @bubblewrap/cli
```

### 2. Inicializar o Projeto Android

Crie uma pasta separada (ex: `android-project`) e rode:

```bash
bubblewrap init --manifest https://seusite.com/manifest.json
```

*(Se você não tiver um manifest online, ele vai pedir os dados manualmente: Nome, Cor, Ícone, URL).*

### 3. Configurar

O Bubblewrap vai fazer perguntas:

- **Domain**: `doispes.streamlit.app`
- **Application Name**: `DoisPés`
- **Short Name**: `DoisPés`
- **Start URL**: `/`
- **Display Mode**: `standalone` (Tela cheia)
- **Status Bar Color**: `#1E1E1E` (Cor do nosso tema)

### 4. Construir o APK/AAB

```bash
bubblewrap build
```

Ele vai baixar o Android SDK e Java automaticamente se você não tiver, e vai gerar:

- `app-release-bundle.aab`: Arquivo pronto para enviar para a Play Store Console.
- `app-release-signed.apk`: Para testar no seu celular.

## 📲 E o Modo Offline?

**Limitação Importante**: Como é um app Streamlit, ele **precisa de internet** para funcionar. O Python roda no servidor, não no celular.

- Se o usuário ficar sem internet, o TWA mostra a tela padrão de "Você está offline" (o Dino do Chrome).

## 🏎️ Melhoria Imediata (PWA)

Antes da Play Store, você pode melhorar a experiência **agora mesmo** adicionando Meta Tags no `app.py` para quem usa "Adicionar à Tela Inicial".

Já adicionei essas tags no código para você. Agora, ao salvar no iPhone/Android:

1. A barra de URL some.
2. A cor do topo fica escura (`#0E1117`).
3. O ícone oficial é usado.

## ❓ Perguntas Frequentes

### "Se eu criar o App, ainda preciso do Streamlit Cloud?"
**SIM! É obrigatório.**
O aplicativo Android (TWA) é apenas uma **janela nativa** que abre o seu site.
- O código Python continua rodando no servidor do Streamlit.
- Se você derrubar o site, o App para de funcionar.
- A vantagem é que **qualquer atualização** que você fizer no código (`git push`) atualiza automaticamente o App de todos os usuários na hora, sem precisar enviar atualização para a Play Store.

### "Posso usar no iPhone (iOS)?"
O TWA é uma tecnologia Android. Para iOS, a Apple não aceita esse tipo de "wrap" fácil na App Store.
No iPhone, o caminho é usar o **"Adicionar à Tela Principal"** (PWA), que já configuramos. Funciona praticamente igual, só não está na loja.

### "Posso distribuir sem a Play Store?" (GitHub Releases)

**SIM!** É uma ótima estratégia inicial.

1. Gere o arquivo `.apk` usando o Bubblewrap.
2. Vá no **GitHub > Releases > Draft a new release**.
3. Crie a versão (ex: `v0.1.0`).
4. **Arraste o arquivo .apk** para a área de anexos.
5. Publique.

Qualquer pessoa com o link pode baixar o `.apk` e instalar (o Android vai avisar que é de "fonte desconhecida", basta autorizar). É perfeito para testes com família e amigos antes de pagar os $25 da Google.

### ⚠️ Dica: Download no Celular (Erro "Ghost" ou 404)
Se o seu repositório for **Privado**, o GitHub protege o download.
- **Problema**: Ao clicar no link pelo WhatsApp/Telegram, ele pode abrir o "GitHub App" deslogado ou um navegador interno.
- **Solução**:
  1. Copie o link da Release.
  2. Abra o **Chrome** no celular.
  3. Garanta que você está **logado no GitHub** no navegador.
  4. Cole o link.
  O download deve começar na hora.
