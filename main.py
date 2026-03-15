import streamlit as st
import sqlite3
import pandas as pd
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida", page_icon="🛡️", layout="centered")

# Criar pasta para fotos se não existir (necessário para o FaceID)
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- BANCO DE DADOS (Versão 2 com Origem e Destino) ---
def conectar():
    # Mudar o nome do arquivo .db força a criação da tabela correta no servidor
    return sqlite3.connect('corrida_protegida_v2.db', check_same_thread=False)

def iniciar_banco():
    conn = conectar()
    cursor = conn.cursor()
    # Tabela de Usuários
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, nome TEXT, 
                       cpf TEXT UNIQUE, senha TEXT, foto TEXT)''')
    # Tabela de Corridas (Agora com Ponto de Origem)
    cursor.execute('''CREATE TABLE IF NOT EXISTS corridas
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, passageiro TEXT, 
                       ponto_origem TEXT, ponto_destino TEXT, status TEXT)''')
    conn.commit()
    conn.close()

iniciar_banco()

# --- CONTROLE DE SESSÃO (Para não deslogar) ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE INICIAL (LOGIN / CADASTRO) ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    st.subheader("Onde o motorista ganha 100% e o passageiro viaja seguro.")
    
    menu = st.sidebar.selectbox("MENU", ["Início", "Sou Motorista", "Sou Passageiro", "Admin"])

    if menu == "Início":
        st.info("Sistema de segurança máxima com FaceID e integração direta com Waze.")
        st.image("https://cdn-icons-png.flaticon.com", width=150)

    elif menu in ["Sou Motorista", "Sou Passageiro"]:
        aba_login, aba_cad = st.tabs(["Login", "Primeiro Acesso"])

        with aba_cad:
            st.write(f"### Cadastro de {menu}")
            nome = st.text_input("Nome Completo")
            cpf = st.text_input("CPF (Apenas números)")
            senha = st.text_input("Crie sua Senha", type="password")
            foto = st.camera_input("Selfie de Segurança (FaceID)")

            if st.button("Finalizar Cadastro"):
                if foto and nome and cpf and senha:
                    caminho_foto = f"fotos/{cpf}.jpg"
                    with open(caminho_foto, "wb") as f:
                        f.write(foto.getbuffer())
                    
                    try:
                        conn = conectar()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (tipo, nome, cpf, senha, foto) VALUES (?,?,?,?,?)",
                                       (menu, nome, cpf, senha, caminho_foto))
                        conn.commit()
                        st.success("✅ Cadastro Realizado! Agora mude para a aba 'Login'.")
                    except:
                        st.error("Erro: Este CPF já está cadastrado.")
                else:
                    st.warning("Preencha todos os campos e tire a selfie!")

        with aba_login:
            st.write(f"### Login {menu}")
            l_cpf = st.text_input("CPF", key="log_cpf")
            l_senha = st.text_input("Senha", type="password", key="log_pass")

            if st.button("Entrar"):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("SELECT nome FROM usuarios WHERE cpf=? AND senha=? AND tipo=?", (l_cpf, l_senha, menu))
                user = cursor.fetchone()
                if user:
                    st.session_state.logado = True
                    st.session_state.user_nome = user[0]
                    st.session_state.user_tipo = menu
                    st.rerun()
                else:
                    st.error("Dados incorretos ou perfil errado.")

    elif menu == "Admin":
        senha_adm = st.text_input("Senha Mestra", type="password")
        if senha_adm == "admin123":
            df = pd.read_sql_query("SELECT tipo, nome, cpf FROM usuarios", conectar())
            st.write("### Usuários Cadastrados")
            st.dataframe(df)

# --- PAINEL PÓS-LOGIN (O QUE APARECE DEPOIS DE ENTRAR) ---
else:
    st.sidebar.button("Sair do App", on_click=logout)
    st.title(f"Bem-vindo, {st.session_state.user_nome}! 🛡️")

    # --- VISÃO DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.markdown("---")
        st.subheader("📍 Solicitar Nova Corrida")
        origem = st.text_input("Onde você está agora?", placeholder="Ex: Rua das Flores, 123, Centro")
        destino = st.text_input("Para onde vamos?", placeholder="Ex: Shopping Central")

        if st.button("CHAMAR MOTORISTA AGORA"):
            if origem and destino:
                conn = conectar()
                conn.execute("INSERT INTO corridas (passageiro, ponto_origem, ponto_destino, status) VALUES (?,?,?,?)",
                             (st.session_state.user_nome, origem, destino, "Aguardando"))
                conn.commit()
                st.success("✅ Chamada enviada! Aguardando um motorista aceitar.")
                st.info("Dica: Fique em local seguro e iluminado.")
            else:
                st.warning("Por favor, preencha a origem e o destino.")

    # --- VISÃO DO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.markdown("---")
        st.subheader("🛣️ Corridas Disponíveis na Região")
        
        # Mostrar corridas pendentes
        df_corridas = pd.read_sql_query("SELECT * FROM corridas WHERE status='Aguardando'", conectar())
        
        if df_corridas.empty:
            st.info("Nenhuma corrida disponível no momento. Fique de prontidão!")
            if st.button("🔄 Atualizar Lista"):
                st.rerun()
        else:
            for index, row in df_corridas.iterrows():
                with st.expander(f"🚩 DE: {row['ponto_origem']}"):
                    st.write(f"**PARA:** {row['ponto_destino']}")
                    st.write(f"**PASSAGEIRO:** {row['passageiro']}")
                    
                    # Link para abrir o WAZE com a Origem já preenchida
                    endereco_waze = row['ponto_origem'].replace(" ", "%20")
                    link_waze = f"https://waze.com{endereco_waze}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{row['id']}"):
                            conn = conectar()
                            conn.execute("UPDATE corridas SET status='Em andamento' WHERE id=?", (row['id'],))
                            conn.commit()
                            st.success("Corrida Aceita!")
                            st.balloons()
                    with col2:
                        # Botão que abre o app do Waze
                        st.markdown(f'''<a href="{link_waze}" target="_blank" style="text-decoration:none;">
                                        <button style="background-color:#33ccff; border:none; color:white; padding:10px; border-radius:5px; width:100%; cursor:pointer;">
                                        🚗 Abrir no Waze</button></a>''', unsafe_allow_html=True)
