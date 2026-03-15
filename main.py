import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")

# CONEXÃO COM SUPABASE (Lê direto dos Secrets)
conn = st.connection("supabase", type=SupabaseConnection)

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
            
            if st.button("Finalizar Cadastro"):
                if nome and cpf and senha:
                    try:
                        # SALVANDO NO SUPABASE (BANCO REAL)
                        conn.table("usuarios").insert([
                            {"tipo": menu, "nome": nome, "cpf": cpf, "senha": senha}
                        ]).execute()
                        st.success("✅ Cadastro Realizado no Banco de Dados Real!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("Preencha todos os campos!")

        with aba_log:
            l_cpf = st.text_input("CPF", key="l_cpf")
            l_pass = st.text_input("Senha", type="password", key="l_pass")
            if st.button("Entrar"):
                # BUSCANDO NO SUPABASE
                res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", menu).execute()
                if res.data:
                    st.session_state.logado = True
                    st.session_state.user_nome = res.data[0]['nome']
                    st.session_state.user_tipo = menu
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

# --- PAINEL PÓS-LOGIN ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Pedir Corrida")
        orig = st.text_input("Localização")
        dest = st.text_input("Destino")
        if st.button("CHAMAR AGORA"):
            conn.table("corridas").insert([
                {"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando"}
            ]).execute()
            st.success("🚀 Chamada enviada para a nuvem!")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Disponíveis")
        res_corridas = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        if not res_corridas.data:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar"): st.rerun()
        else:
            for r in res_corridas.data:
                with st.expander(f"🚩 DE: {r['ponto_origem']}"):
                    st.write(f"**PARA:** {r['ponto_destino']}")
                    end_waze = urllib.parse.quote(r['ponto_origem'])
                    link_waze = f"https://waze.com{end_waze}&navigate=yes"
                    if st.button(f"✅ Aceitar #{r['id']}"):
                        conn.table("corridas").update({"status": "Em curso"}).eq("id", r['id']).execute()
                        st.success("Corrida aceita!"); st.balloons()
                    st.markdown(f'[🚗 Abrir no Waze]({link_waze})')
