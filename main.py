import streamlit as st
import sqlite3
import pandas as pd
import os
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida", page_icon="🛡️", layout="centered")

# Pasta para as fotos do FaceID
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- BANCO DE DADOS (Versão 3) ---
def conectar():
    return sqlite3.connect('corrida_v3.db', check_same_thread=False)

def iniciar_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, nome TEXT, 
                       cpf TEXT UNIQUE, senha TEXT, foto TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS corridas
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, passageiro TEXT, 
                       ponto_origem TEXT, ponto_destino TEXT, status TEXT)''')
    conn.commit()
    conn.close()

iniciar_banco()

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE DE ACESSO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    menu = st.sidebar.selectbox("MENU", ["Início", "Sou Motorista", "Sou Passageiro", "Admin"])

    if menu == "Início":
        st.info("Segurança Total: Motorista 100% | Passageiro Protegido")
        st.image("https://cdn-icons-png.flaticon.com", width=120)

    elif menu in ["Sou Motorista", "Sou Passageiro"]:
        aba_log, aba_cad = st.tabs(["Login", "Cadastro"])
        
        with aba_cad:
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF (números)")
            senha = st.text_input("Senha", type="password")
            foto = st.camera_input("Selfie FaceID")
            if st.button("Cadastrar"):
                if foto and nome and cpf and senha:
                    caminho = f"fotos/{cpf}.jpg"
                    with open(caminho, "wb") as f: f.write(foto.getbuffer())
                    try:
                        conn = conectar(); cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (tipo, nome, cpf, senha, foto) VALUES (?,?,?,?,?)",
                                       (menu, nome, cpf, senha, caminho))
                        conn.commit(); conn.close()
                        st.success("✅ Pronto! Faça login.")
                    except: st.error("CPF já existe.")
                else: st.warning("Preencha tudo!")

        with aba_log:
            l_cpf = st.text_input("CPF", key="l_cpf")
            l_pass = st.text_input("Senha", type="password", key="l_pass")
            if st.button("Entrar"):
                conn = conectar(); cursor = conn.cursor()
                cursor.execute("SELECT nome FROM usuarios WHERE cpf=? AND senha=? AND tipo=?", (l_cpf, l_pass, menu))
                user = cursor.fetchone()
                if user:
                    st.session_state.logado = True
                    st.session_state.user_nome = user[0]
                    st.session_state.user_tipo = menu
                    st.rerun()
                else: st.error("Dados incorretos.")

    elif menu == "Admin":
        if st.text_input("Senha Admin", type="password") == "admin123":
            st.dataframe(pd.read_sql_query("SELECT * FROM usuarios", conectar()))

# --- PAINEL DO USUÁRIO ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # --- BOTÃO DE PÂNICO SOS (Para ambos) ---
    with st.sidebar:
        st.markdown("---")
        st.error("🚨 EMERGÊNCIA")
        msg_sos = urllib.parse.quote(f"SOCORRO! Preciso de ajuda na Corrida Protegida. Sou {st.session_state.user_nome}.")
        link_sos = f"https://wa.me{msg_sos}" # Troque pelo seu número
        st.markdown(f'<a href="{link_sos}" target="_blank"><button style="background-color:red; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-weight:bold; cursor:pointer;">🆘 ACIONAR POLÍCIA / SOS</button></a>', unsafe_allow_html=True)

    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Pedir Corrida")
        orig = st.text_input("Sua Localização (Rua, Nº, Bairro)")
        dest = st.text_input("Destino Final")
        if st.button("CHAMAR AGORA"):
            if orig and dest:
                conn = conectar()
                conn.execute("INSERT INTO corridas (passageiro, ponto_origem, ponto_destino, status) VALUES (?,?,?,?)",
                             (st.session_state.user_nome, orig, dest, "Aguardando"))
                conn.commit()
                st.success("🚀 Chamada enviada! Aguarde o motorista.")
            else: st.warning("Informe origem e destino.")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas para Você")
        df = pd.read_sql_query("SELECT * FROM corridas WHERE status='Aguardando'", conectar())
        if df.empty:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar"): st.rerun()
        else:
            for i, r in df.iterrows():
                with st.expander(f"🚩 DE: {r['ponto_origem']}"):
                    st.write(f"**PARA:** {r['ponto_destino']}")
                    
                    # LINK WAZE CORRIGIDO
                    end_waze = urllib.parse.quote(r['ponto_origem'])
                    link_waze = f"https://waze.com{end_waze}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}"):
                            conn = conectar()
                            conn.execute("UPDATE corridas SET status='Em curso' WHERE id=?", (r['id'],))
                            conn.commit()
                            st.success("Aceito!"); st.balloons()
                    with col2:
                        st.markdown(f'<a href="{link_waze}" target="_blank"><button style="background-color:#33ccff; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer;">🚗 Ir ao Waze</button></a>', unsafe_allow_html=True)
