import streamlit as st
import sqlite3
import pandas as pd
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida", page_icon="🛡️")

# Criar pasta para fotos se não existir
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- BANCO DE DADOS ---
def conectar():
    conn = sqlite3.connect('corrida_protegida.db', check_same_thread=False)
    return conn

def iniciar_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, nome TEXT, cpf TEXT UNIQUE, senha TEXT, foto TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS corridas
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, passageiro TEXT, destino TEXT, status TEXT)''')
    conn.commit()
    conn.close()

iniciar_banco()

# --- CONTROLE DE SESSÃO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

# --- LOGOUT ---
def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    menu = st.sidebar.selectbox("MENU", ["Início", "Sou Motorista", "Sou Passageiro", "Admin"])

    if menu == "Início":
        st.write("### Bem-vindo ao Sistema de Segurança Máxima")
        st.info("Onde motoristas ganham 100% e passageiros viajam protegidos.")
        st.image("https://img.icons8.com")

    elif menu in ["Sou Motorista", "Sou Passageiro"]:
        aba_login, aba_cad = st.tabs(["Login", "Primeiro Acesso"])

        with aba_cad:
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF (apenas números)")
            senha = st.text_input("Senha", type="password")
            foto = st.camera_input("Selfie de Segurança")

            if st.button("Finalizar Cadastro"):
                if foto and nome and cpf:
                    caminho_foto = f"fotos/{cpf}.jpg"
                    with open(caminho_foto, "wb") as f:
                        f.write(foto.getbuffer())
                    
                    try:
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (tipo, nome, cpf, senha, foto) VALUES (?,?,?,?,?)",
                                       (menu, nome, cpf, senha, caminho_foto))
                        conn.commit()
                        st.success("✅ Cadastro Realizado! Faça o Login agora.")
                    except:
                        st.error("Erro: CPF já cadastrado.")
                else:
                    st.warning("Preencha tudo e tire a foto!")

        with aba_login:
            l_cpf = st.text_input("CPF", key="l_cpf")
            l_senha = st.text_input("Senha", type="password", key="l_pass")
            if st.button("Entrar"):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("SELECT nome, tipo FROM usuarios WHERE cpf=? AND senha=? AND tipo=?", (l_cpf, l_senha, menu))
                user = cursor.fetchone()
                if user:
                    st.session_state.logado = True
                    st.session_state.user_nome = user[0]
                    st.session_state.user_tipo = user[1]
                    st.rerun()
                else:
                    st.error("CPF ou Senha incorretos.")

    elif menu == "Admin":
        adm_pass = st.text_input("Senha Mestra", type="password")
        if adm_pass == "admin123":
            df = pd.read_sql_query("SELECT * FROM usuarios", conectar())
            st.dataframe(df)

# --- PAINEL PÓS-LOGIN ---
else:
    st.sidebar.button("Sair/Logout", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 👋")
    st.subheader(f"Painel do {st.session_state.user_tipo}")

    if st.session_state.user_tipo == "Sou Passageiro":
        st.write("---")
        destino = st.text_input("Para onde você quer ir?")
        if st.button("Solicitar Corrida Protegida 🛡️"):
            if destino:
                conn = conectar()
                conn.execute("INSERT INTO corridas (passageiro, destino, status) VALUES (?,?,?)", 
                             (st.session_state.user_nome, destino, "Aguardando"))
                conn.commit()
                st.success(f"Chamada enviada! Destino: {destino}. Aguarde um motorista.")
            else:
                st.warning("Digite o destino primeiro.")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.write("---")
        st.write("### Corridas Disponíveis agora:")
        df_corridas = pd.read_sql_query("SELECT * FROM corridas WHERE status='Aguardando'", conectar())
        
        if df_corridas.empty:
            st.info("Nenhuma corrida pendente no momento.")
            if st.button("🔄 Atualizar Lista"):
                st.rerun()
        else:
            for index, row in df_corridas.iterrows():
                with st.expander(f"📍 Destino: {row['destino']}"):
                    st.write(f"Passageiro: {row['passageiro']}")
                    if st.button(f"Aceitar Corrida #{row['id']}"):
                        conn = conectar()
                        conn.execute("UPDATE corridas SET status='Em andamento' WHERE id=?", (row['id'],))
                        conn.commit()
                        st.success("Corrida Aceita! Vá ao ponto de encontro.")
                        st.balloons()
