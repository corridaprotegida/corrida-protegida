import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")

# CONEXÃO COM SUPABASE (Lê dos Secrets)
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
    aba_log, aba_cad = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with aba_cad:
        tipo = st.radio("Seu perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (números)").replace(".", "").replace("-", "").strip()
        senha = st.text_input("Crie uma Senha", type="password").strip()
        if st.button("Finalizar Cadastro"):
            if nome and cpf and senha:
                try:
                    conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                    st.success("✅ Cadastro Realizado! Vá para a aba Entrar.")
                except: st.error("Erro: CPF já cadastrado.")
            else: st.warning("Preencha todos os campos!")

    with aba_log:
        tipo_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tipo_l")
        l_cpf = st.text_input("CPF", key="l_cpf").replace(".", "").replace("-", "").strip()
        l_pass = st.text_input("Senha", type="password", key="l_pass").strip()
        if st.button("Acessar Painel"):
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", tipo_l).execute()
            
            if res.data and len(res.data) > 0:
                st.session_state.logado = True
                # Pega o nome do primeiro registro encontrado
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = tipo_l
                st.rerun()
            else:
                st.error("⚠️ Dados incorretos ou perfil errado.")

# --- PAINEL DO USUÁRIO LOGADO ---
else:
    st.sidebar.button("Sair/Logout", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # --- TELA DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Sua Corrida")
        
        # Busca a última corrida não finalizada do passageiro
        res_ativa = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res_ativa.data:
            c = res_ativa.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Aguardando um motorista aceitar...")
                if st.button("🔄 Atualizar Status"): st.rerun()
            elif c['status'] == "Em curso":
                mot = c.get('motorista_nome') or "Um motorista"
                st.success(f"✅ O motorista **{mot}** aceitou sua corrida!")
                st.info(f"De: {c['ponto_origem']} ➡️ Para: {c['ponto_destino']}")
                if st.button("🏁 Finalizar Corrida (Cheguei!)"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
        else:
            origem = st.text_input("🏠 Onde você está?")
            destino = st.text_input("🏁 Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                if origem and destino:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome,
                        "ponto_origem": origem, 
                        "ponto_destino": destino, 
                        "status": "Aguardando"
                    }]).execute()
                    st.rerun()

    # --- TELA DO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Disponíveis")
        res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res_c.data:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar Lista"): st.rerun()
        else:
            for r in res_c.data:
                with st.expander(f"🚩 DE: {r['ponto_origem']}"):
                    st.write(f"**PARA:** {r['ponto_destino']}")
                    st.write(f"**PASSAGEIRO:** {r['passageiro']}")
                    
                    # --- LINK GOOGLE MAPS CORRIGIDO ---
                    end_maps = urllib.parse.quote(r['ponto_origem'])
                    link_maps = f"https://www.google.com{end_maps}"
                    
                    if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                        conn.table("corridas").update({
                            "status": "Em curso", 
                            "motorista_nome": st.session_state.user_nome
                        }).eq("id", r['id']).execute()
                        st.success("Corrida Aceita! O passageiro foi avisado."); st.balloons()
                        time.sleep(1)
                        st.rerun()
                    
                    st.markdown(f'''<a href="{link_maps}" target="_blank" style="text-decoration:none;">
                                    <div style="background-color:#4285F4; color:white; padding:12px; border-radius:8px; text-align:center; font-weight:bold;">
                                    📍 Abrir no Google Maps</div></a>''', unsafe_allow_html=True)

    # --- BOTÃO DE PÂNICO SOS ---
    st.sidebar.markdown("---")
    msg_sos = urllib.parse.quote(f"SOS! Sou {st.session_state.user_nome} e preciso de ajuda agora!")
    st.sidebar.markdown(f'''<a href="https://wa.me{msg_sos}" target="_blank">
                        <button style="background-color:red; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-weight:bold; cursor:pointer;">
                        🆘 BOTÃO DE PÂNICO</button></a>''', unsafe_allow_html=True)
