import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")

# CONEXÃO COM SUPABASE
conn = st.connection("supabase", type=SupabaseConnection)

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE DE ACESSO (LOGIN/CADASTRO) ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    aba_log, aba_cad = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with aba_cad:
        tipo = st.radio("Seu perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        # Limpamos o CPF para salvar apenas números
        cpf = st.text_input("CPF (apenas números)").replace(".", "").replace("-", "").strip()
        senha = st.text_input("Crie uma Senha", type="password").strip()
        
        if st.button("Finalizar Cadastro"):
            if nome and cpf and senha:
                try:
                    conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                    st.success("✅ Cadastro Realizado! Agora vá para a aba Login.")
                except: 
                    st.error("Erro: Este CPF já pode estar cadastrado ou houve falha na conexão.")
            else: 
                st.warning("Preencha todos os campos corretamente!")

    with aba_log:
        tipo_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tipo_l")
        l_cpf = st.text_input("CPF", key="l_cpf").replace(".", "").replace("-", "").strip()
        l_pass = st.text_input("Senha", type="password", key="l_pass").strip()
        
        if st.button("Acessar Painel"):
            # Busca no Supabase
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", tipo_l).execute()
            
            # CORREÇÃO DO LOGIN: Verifica se a lista 'data' tem conteúdo
            if res.data and len(res.data) > 0:
                st.session_state.logado = True
                # Pegamos o nome do primeiro item da lista [0]
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = tipo_l
                st.rerun()
            else:
                st.error("⚠️ Dados incorretos ou perfil errado. Verifique se selecionou o tipo certo (Passageiro/Motorista).")

# --- PAINEL DO USUÁRIO LOGADO ---
else:
    st.sidebar.button("Sair/Logout", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")
    st.write(f"Conectado como: **{st.session_state.user_tipo}**")

    # --- TELA DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.markdown("---")
        st.subheader("📍 Solicitar Nova Corrida")
        origem = st.text_input("🏠 Onde você está?", placeholder="Ex: Rua São Bento, 450")
        destino = st.text_input("🏁 Para onde vamos?", placeholder="Ex: Shopping Iguatemi")
        
        if st.button("CHAMAR AGORA 🚀"):
            if origem and destino:
                try:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome,
                        "ponto_origem": origem,
                        "ponto_destino": destino,
                        "status": "Aguardando"
                    }]).execute()
                    st.success("🚀 Chamada enviada! Aguarde um motorista aceitar.")
                except:
                    st.error("Erro ao enviar chamada. Tente novamente.")
            else: 
                st.warning("Informe a origem e o destino!")

    # --- TELA DO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.markdown("---")
        st.subheader("🛣️ Corridas Disponíveis")
        
        # Busca corridas com status Aguardando
        res_corridas = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res_corridas.data:
            st.info("Buscando passageiros próximos...")
            if st.button("🔄 Atualizar Lista"): 
                st.rerun()
        else:
            for r in res_corridas.data:
                with st.expander(f"🚩 Origem: {r['ponto_origem']}"):
                    st.write(f"**DESTINO:** {r['ponto_destino']}")
                    st.write(f"**PASSAGEIRO:** {r['passageiro']}")
                    
                    # LINK DO WAZE (Trata o endereço para não dar erro de caracteres)
                    end_waze = urllib.parse.quote(r['ponto_origem'])
                    link_waze = f"https://www.waze.com{end_waze}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({"status": "Em curso"}).eq("id", r['id']).execute()
                            st.success("Corrida Aceita!")
                            st.balloons()
                    with col2:
                        st.markdown(f'''<a href="{link_waze}" target="_blank" style="text-decoration: none;">
                                        <div style="background-color: #33ccff; color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold;">
                                            🚗 Abrir no Waze
                                        </div></a>''', unsafe_allow_html=True)

    # --- BOTÃO DE PÂNICO SOS ---
    st.sidebar.markdown("---")
    msg_sos = urllib.parse.quote(f"SOCORRO! Sou {st.session_state.user_nome} e preciso de ajuda agora!")
    st.sidebar.markdown(f'''<a href="https://wa.me{msg_sos}" target="_blank">
                        <button style="background-color:red; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-weight:bold; cursor:pointer;">
                        🆘 BOTÃO DE PÂNICO</button></a>''', unsafe_allow_html=True)
