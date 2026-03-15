import streamlit as st
import sqlite3
import pandas as pd
import os

# --- CONFIGURAÇÃO E PASTAS ---
st.set_page_config(page_title="Corrida Protegida", page_icon="🛡️", layout="centered")

if not os.path.exists("fotos_usuarios"):
    os.makedirs("fotos_usuarios")

# --- FUNÇÕES DE BANCO DE DADOS ---
def conectar():
    return sqlite3.connect('corrida_protegida_web.db', check_same_thread=False)

def iniciar_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, nome TEXT, 
                       cpf TEXT UNIQUE, senha TEXT, foto_face TEXT)''')
    # Tabela simples para simular corridas
    cursor.execute('''CREATE TABLE IF NOT EXISTS corridas
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, passageiro TEXT, 
                       ponto_origem TEXT, status TEXT)''')
    conn.commit()
    conn.close()

iniciar_banco()

# --- CONTROLE DE SESSÃO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.log_status = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

# --- INTERFACE LATERAL ---
st.sidebar.title("🛡️ Corrida Protegida")
if st.session_state.log_status:
    st.sidebar.success(f"Logado como: {st.session_state.user_nome}")
    if st.sidebar.button("Sair"):
        st.session_state.log_status = False
        st.rerun()
else:
    menu = st.sidebar.selectbox("MENU", ["Início", "Sou Motorista", "Sou Passageiro", "Admin"])

# --- PÁGINA INICIAL ---
if not st.session_state.log_status:
    if menu == "Início":
        st.title("🛡️ BEM-VINDO")
        st.info("Segurança máxima para quem dirige e para quem viaja.")
        st.image("https://cdn-icons-png.flaticon.com", width=200)

    elif menu in ["Sou Motorista", "Sou Passageiro"]:
        aba_login, aba_cad = st.tabs(["Login", "Cadastro"])

        with aba_cad:
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF (Apenas números)")
            senha = st.text_input("Senha", type="password")
            foto = st.camera_input("Selfie de Segurança")

            if st.button("Finalizar Cadastro", key="btn_cad"):
                if foto and nome and cpf and senha:
                    caminho_foto = f"fotos_usuarios/{cpf}.jpg"
                    with open(caminho_foto, "wb") as f:
                        f.write(foto.getbuffer())
                    
                    try:
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (tipo, nome, cpf, senha, foto_face) VALUES (?,?,?,?,?)",
                                       (menu, nome, cpf, senha, caminho_foto))
                        conn.commit()
                        st.success("✅ Cadastro realizado! Vá para a aba de Login.")
                    except:
                        st.error("❌ CPF já cadastrado.")
                else:
                    st.warning("Preencha todos os campos e tire a foto!")

        with aba_login:
            l_cpf = st.text_input("CPF", key="l_cpf")
            l_senha = st.text_input("Senha", type="password", key="l_senha")
            if st.button("Entrar"):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("SELECT nome, tipo FROM usuarios WHERE cpf=? AND senha=? AND tipo=?", (l_cpf, l_senha, menu))
                user = cursor.fetchone()
                if user:
                    st.session_state.log_status = True
                    st.session_state.user_nome = user[0]
                    st.session_state.user_tipo = user[1]
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

    elif menu == "Admin":
        senha_adm = st.text_input("Senha Mestra", type="password")
        if senha_adm == "admin123":
            df = pd.read_sql_query("SELECT tipo, nome, cpf FROM usuarios", conectar())
            st.dataframe(df)

# --- ÁREA LOGADA ---
else:
    st.title(f"Painel do {st.session_state.user_tipo}")
    
    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("Solicitar Nova Corrida")
        destino = st.text_input("Para onde vamos?")
        if st.button("Chamar Agora"):
            conn = conectar()
            conn.execute("INSERT INTO corridas (passageiro, ponto_origem, status) VALUES (?,?,?)",
                         (st.session_state.user_nome, destino, "Aguardando"))
            conn.commit()
            st.success("Chamada enviada! Aguardando motorista...")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("Corridas Disponíveis")
        df_corridas = pd.read_sql_query("SELECT * FROM corridas WHERE status='Aguardando'", conectar())
        if not df_corridas.empty:
            st.table(df_corridas)
            id_corrida = st.number_input("ID da Corrida para aceitar", step=1)
            if st.button("Aceitar Corrida"):
                st.info(f"Corrida {id_corrida} aceita! Navegando via GPS...")
        else:
            st.write("Nenhuma corrida no momento. Fique alerta! 🛡️")
