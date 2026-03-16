import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualiza a tela a cada 5 segundos para sincronizar motorista e passageiro
st_autorefresh(interval=5000, key="global_refresh")

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None

def logout():
    if st.session_state.user_cpf:
        conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="r_tp")
        n = st.text_input("Nome Completo", key="r_n")
        c = st.text_input("CPF (apenas números)", key="r_c")
        pix = st.text_input("Chave PIX", key="r_pix") if tp == "Sou Motorista" else ""
        s = st.text_input("Senha", type="password", key="r_s")
        if st.button("Finalizar Cadastro", key="btn_reg"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
                st.success("✅ Cadastrado! Vá em Entrar.")
            else: st.warning("Preencha todos os campos!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="l_tp")
        lc = st.text_input("CPF", key="l_c")
        ls = st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar", key="btn_log"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.user_cpf, st.session_state.user_nome, st.session_state.user_tipo = u['cpf'], u['nome'], u['tipo']
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_logout")

    # --- VISÃO MOTORISTA ---
    if st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # GPS em tempo real: Atualiza o banco se o motorista estiver em corrida
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        st.subheader("Chamadas Disponíveis")
        corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
        
        if not corridas.data:
            st.info("Nenhuma chamada no momento. Aguarde...")

        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}** | R$ {r['valor_total']:.2f}")
                st.caption(f"🏁 Destino: {r['ponto_destino']}")
                
                # LINK PARA ABRIR APP WAZE NO CELULAR
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'''
                    <a href="waze://?q={addr}&navigate=yes">
                        <button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:10px;">
                            🚀 ABRIR NO APP WAZE
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
                
                if st.button(f"Aceitar Corrida #{r['id']}", key=f"acc_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO PASSAGEIRO ---
    elif st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status Atual: **{c['status']}**")
            
            if c['status'] == "Confirmada" and c['lat_motorista']:
                st.subheader(f"🚖 {c['motorista_nome']} está a caminho!")
                df_mapa = pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]})
                st.map(df_mapa)
                
                # Exibe PIX do motorista
                m_info = conn.table("usuarios").select("chave_pix").eq("nome", c['motorista_nome']).execute()
                if m_info.data:
                    st.warning(f"PIX do Motorista: `{m_info.data[0]['chave_pix']}`")

            if st.button("Cancelar Corrida ❌", key="pax_cancel"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o = st.text_input("Onde você está?", key="pax_ori")
            d = st.text_input("Para onde vamos?", key="pax_dest")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0, key="pax_val")
            if st.button("SOLICITAR AGORA 🚀", key="pax_btn"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

