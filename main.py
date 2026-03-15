import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=BaseComponent=SupabaseConnection)

if "logado" not in st.session_state:
    st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = False, "", ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- LOGIN/CADASTRO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    tab_log, tab_cad = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with tab_cad:
        t = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("Finalizar Cadastro"):
            conn.table("usuarios").insert([{"tipo": t, "nome": n, "cpf": c, "senha": s}]).execute()
            st.success("✅ Cadastrado!")
    with tab_log:
        tl = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tl")
        lc, ls = st.text_input("CPF", key="lc"), st.text_input("Senha", type="password", key="ls")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("nome").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = True, r.data[0]['nome'], tl
                st.rerun()

# --- PAINEL LOGADO ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando": st.warning("⏳ Buscando motorista...")
            else: st.success(f"✅ Motorista {c.get('motorista_nome')} a caminho!"); st.info(f"De: {c['ponto_origem']}")
            if st.button("🏁 Cheguei"): 
                conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("🏠 Onde você está?"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "status": "Aguardando"}]).execute()
                st.rerun()

    elif st.session_state.user_tipo == "Sou Motorista":
        res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        if not res_c.data: st.info("Buscando passageiros..."); st.button("🔄 Atualizar")
        else:
            for r in res_c.data:
                with st.container(border=True):
                    st.write(f"👤 **{r['passageiro']}**")
                    st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                    
                    # --- MINI MAPA VISUAL (Google Static Maps Alternativo) ---
                    # Mostra uma imagem do local para o motorista se localizar antes de abrir o GPS
                    map_url = f"https://www.google.com"
                    st.image(f"https://maps.googleapis.com{urllib.parse.quote(r['ponto_origem'])}&zoom=15&size=400x200&sensor=false", caption="Localização aproximada do passageiro")

                    # --- BOTÕES DE NAVEGAÇÃO REAL (Deep Links) ---
                    end = urllib.parse.quote(r['ponto_origem'])
                    
                    # Link que FORÇA o Google Maps App
                    link_google = f"google.navigation:q={end}"
                    # Link que FORÇA o Waze App
                    link_waze = f"waze://?q={end}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}"):
                            conn.table("corridas").update({"status": "Em curso", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                            st.rerun()
                    with col2:
                        # Botão estilizado para abrir os APPS direto no celular
                        st.markdown(f"""
                            <a href="{link_waze}"><button style="background:#33ccff;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;">🚗 Abrir no WAZE</button></a>
                            <div style='margin-top:5px'></div>
                            <a href="{link_google}"><button style="background:#4285F4;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;">📍 Abrir no MAPS</button></a>
                        """, unsafe_allow_html=True)
