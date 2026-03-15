import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- ACESSO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    aba_log, aba_cad = st.tabs(["🔐 Login", "📝 Cadastro"])
    
    with aba_cad:
        tipo = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (números)")
        senha = st.text_input("Senha", type="password")
        if st.button("Cadastrar"):
            if nome and cpf and senha:
                conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                st.success("✅ Sucesso! Vá ao Login.")
            else: st.warning("Preencha tudo!")

    with aba_log:
        t_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        l_cpf = st.text_input("CPF", key="l_cpf")
        l_pass = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Entrar"):
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", t_l).execute()
            if res.data:
                st.session_state.logado = True
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = t_l
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Solicitar Corrida")
        origem = st.text_input("🏠 Onde você está?", placeholder="Ex: Rua das Flores, 123 - Centro")
        destino = st.text_input("🏁 Para onde vamos?", placeholder="Ex: Rodoviária ou Shopping")
        
        if st.button("CHAMAR AGORA 🚀"):
            if origem and destino:
                conn.table("corridas").insert([{
                    "passageiro": st.session_state.user_nome,
                    "ponto_origem": origem,
                    "ponto_destino": destino,
                    "status": "Aguardando"
                }]).execute()
                st.success("🚀 Chamada enviada! Aguarde o motorista.")
            else: st.warning("Preencha Origem e Destino!")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Disponíveis")
        res = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res.data:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar"): st.rerun()
        else:
            for r in res.data:
                with st.expander(f"🚩 DE: {r['ponto_origem']}"):
                    st.write(f"**PARA:** {r['ponto_destino']}")
                    st.write(f"**PASSAGEIRO:** {r['passageiro']}")
                    
                    # LINK OFICIAL WAZE
                    end_waze = urllib.parse.quote(r['ponto_origem'])
                    link_waze = f"https://www.waze.com{end_waze}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}"):
                            conn.table("corridas").update({"status": "Em curso"}).eq("id", r['id']).execute()
                            st.success("Aceito!"); st.balloons()
                    with col2:
                        st.markdown(f'''<a href="{link_waze}" target="_blank" style="text-decoration:none;">
                                        <div style="background-color:#33ccff; color:white; padding:10px; border-radius:5px; text-align:center; font-weight:bold;">
                                        🚗 Abrir Waze</div></a>''', unsafe_allow_html=True)

    # BOTÃO SOS
    st.sidebar.markdown("---")
    msg_sos = urllib.parse.quote(f"SOCORRO! Sou {st.session_state.user_nome} e preciso de ajuda!")
    st.sidebar.markdown(f'<a href="https://wa.me{msg_sos}" target="_blank"><button style="background-color:red; color:white; border:none; padding:10px; width:100%; border-radius:5px; cursor:pointer;">🆘 BOTÃO DE PÂNICO</button></a>', unsafe_allow_html=True)
