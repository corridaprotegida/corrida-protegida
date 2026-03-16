import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation # Necessário: pip install streamlit-js-eval
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="cad_tp")
        n = st.text_input("Nome Completo", key="cad_n")
        c = st.text_input("CPF", key="cad_c")
        s = st.text_input("Senha", type="password", key="cad_s")
        if st.button("Finalizar Cadastro", key="btn_cad"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 2.00}]).execute()
                st.success("✅ Cadastrado!")
            else: st.warning("Preencha tudo!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="log_tp")
        lc = st.text_input("CPF", key="log_c")
        ls = st.text_input("Senha", type="password", key="log_s")
        if st.button("Acessar", key="btn_log"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                user = r.data[0]
                st.session_state.user_cpf, st.session_state.user_nome, st.session_state.user_tipo = user['cpf'], user['nome'], user['tipo']
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    st.sidebar.button("🚪 Sair", on_click=logout, key="btn_out")

    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: {c['status']}")
            if st.button("Cancelar ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            # --- GEOLOCALIZAÇÃO ---
            if st.checkbox("📍 Usar minha localização atual"):
                loc = get_geolocation()
                if loc:
                    lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
                    st.success(f"Localizado! Lat: {lat}, Lon: {lon}")
                    origem_sugerida = f"{lat}, {lon}"
                else:
                    st.warning("Aguardando permissão do navegador...")
                    origem_sugerida = ""
            else:
                origem_sugerida = ""

            o = st.text_input("Onde você está?", value=origem_sugerida, key="in_o")
            d = st.text_input("Para onde vamos?", key="in_d")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0, key="in_v")
            if st.button("SOLICITAR 🚀"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 {r['passageiro']} | 💰 R$ {r['valor_total']}")
                st.write(f"De: {r['ponto_origem']} ➡️ Para: {r['ponto_destino']}")
                if st.button(f"Aceitar Corrida #{r['id']}", key=f"acc_{r['id']}"):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()
