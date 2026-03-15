import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse
import time

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

# --- INTERFACE DE ACESSO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    aba_log, aba_cad = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with aba_cad:
        tipo = st.radio("Seu perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (números)").replace(".", "").replace("-", "").strip()
        senha = st.text_input("Senha", type="password").strip()
        if st.button("Finalizar Cadastro"):
            if nome and cpf and senha:
                try:
                    conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                    st.success("✅ Cadastro Realizado!")
                except: st.error("Erro: CPF já existe.")

    with aba_log:
        tipo_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tipo_l")
        l_cpf = st.text_input("CPF", key="l_cpf")
        l_pass = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Painel"):
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", tipo_l).execute()
            if res.data and len(res.data) > 0:
                st.session_state.logado = True
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = tipo_l
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # --- TELA DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Sua Corrida")
        
        # Checa se o passageiro já tem uma corrida ativa
        res_ativa = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res_ativa.data:
            corrida = res_ativa.data[0]
            if corrida['status'] == "Aguardando":
                st.warning("⏳ Aguardando um motorista aceitar...")
                if st.button("🔄 Checar se alguém aceitou"): st.rerun()
            elif corrida['status'] == "Em curso":
                st.success(f"✅ O motorista **{corrida.get('motorista_nome', 'Alguém')}** aceitou sua corrida!")
                st.info(f"Origem: {corrida['ponto_origem']} ➡️ Destino: {corrida['ponto_destino']}")
        else:
            origem = st.text_input("🏠 Onde você está?")
            destino = st.text_input("🏁 Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                if origem and destino:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome,
                        "ponto_origem": origem, "ponto_destino": destino, "status": "Aguardando"
                    }]).execute()
                    st.rerun()

    # --- TELA DO MOTORISTA ---
        elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Disponíveis")
        res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res_c.data:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar"): st.rerun()
        else:
            for r in res_c.data:
                with st.expander(f"🚩 DE: {r['ponto_origem']}"):
                    st.write(f"**DESTINO:** {r['ponto_destino']}")
                    
                    # --- LINK CORRIGIDO DO GOOGLE MAPS ---
                    # A barra "/" após o .com e o "?q=" são obrigatórios
                    endereco_formatado = urllib.parse.quote(r['ponto_origem'])
                    link_maps = f"https://www.google.com{endereco_formatado}"
                    
                    if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                        # Registra que este motorista aceitou
                        conn.table("corridas").update({
                            "status": "Em curso", 
                            "motorista_nome": st.session_state.user_nome
                        }).eq("id", r['id']).execute()
                        st.success("Corrida Aceita!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    
                    # Botão azul do Google Maps
                    st.markdown(f'''<a href="{link_maps}" target="_blank" style="text-decoration:none;">
                                    <div style="background-color:#4285F4; color:white; padding:12px; border-radius:8px; text-align:center; font-weight:bold;">
                                    📍 Abrir Navegação no Google Maps</div></a>''', unsafe_allow_html=True)
