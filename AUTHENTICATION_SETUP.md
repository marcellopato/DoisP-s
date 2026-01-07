# 🔐 Guia de Configuração - Autenticação Segura

## O que mudou?

✅ **Autenticação segura implementada!**

Agora o DoisPés usa:
- Login com email **E SENHA** (antes era só email)
- Validação de senha forte (8+ chars, letras e números)
- Recuperação de senha via email
- Proteção contra tentativas excessivas

---

## 🔧 Configuração Necessária

### 1. Adicionar FIREBASE_API_KEY

Para o login funcionar, você precisa adicionar a **Web API Key** do Firebase no arquivo `.streamlit/secrets.toml`.

#### Como obter a chave:

1. Acesse: https://console.firebase.google.com/
2. Selecione seu projeto
3. Clique na **engrenagem** (configurações) → **Configurações do projeto**
4. Role até **Seus aplicativos** → **SDK snippet**
5. Escolha **Config**
6. Copie o valor de `apiKey`

Exemplo:
```javascript
const firebaseConfig = {
  apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  // ← Esta aqui!
  authDomain: "...",
  // ...
};
```

#### Adicione ao secrets.toml:

```toml
GEMINI_KEY = "sua_chave_gemini"
FIREBASE_KEY = '{"type": "service_account", ...}'

# Nova configuração
FIREBASE_API_KEY = "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

---

## ✅ Testar Autenticação

### 1. Criar conta de teste:

```bash
streamlit run app.py
```

1. Vá na aba **"Nova Conta"**
2. Preencha:
   - Email: `teste@example.com`
   - Senha: `senha123` (mínimo 8 chars, com letras e números)
   - Código da Família: `TESTE`
3. Clique em **"Cadastrar"**

### 2. Fazer login:

1. Vá na aba **"Entrar"**
2. Digite email e senha
3. Clique em **"Entrar"**

### 3. Testar recuperação de senha:

1. Vá na aba **"Esqueci a Senha"**
2. Digite o email
3. Clique em **"Enviar Link de Recuperação"**
4. Verifique a caixa de entrada (pode cair no spam)

---

## 🔒 Segurança

### Validação de senha:
- ✅ Mínimo 8 caracteres
- ✅ Pelo menos 1 letra
- ✅ Pelo menos 1 número

### Proteção:
- ✅ Senha armazenada com hash no Firebase
- ✅ Proteção contra força bruta (rate limiting)
- ✅ Tokens de sessão seguros
- ✅ Recuperação via email oficial do Firebase

---

## 🐛 Troubleshooting

### Erro: "Configuração incompleta"

**Causa**: `FIREBASE_API_KEY` não configurada

**Solução**: Siga o passo 1 acima

### Erro: "Email ou senha incorretos"

**Causas possíveis**:
1. Senha digitada errada
2. Email não cadastrado
3. Conta ainda não criada

**Solução**: Verifique os dados ou crie uma nova conta

### Emails de recuperação caem no spam

**Solução**: 
1. Verifique a pasta spam
2. Adicione `noreply@[SEU-PROJETO].firebaseapp.com` aos contatos

---

## 📝 Próximos Passos

- [ ] Testar criação de conta
- [ ] Testar login
- [ ] Testar recuperação de senha
- [ ] Adicionar validação de autorização nas queries (próxima tarefa)
