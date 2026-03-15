import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import extra_streamlit_components as stx # Para Cookies
import urllib.parse
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)
cookie_manager = stx.CookieManager()

# --- SISTEMA DE LOGIN COM COOKIES ---
if "logado" not in st.session_state:
    saved_user = cookie_manager.get(cookie="user_cpf")
    if saved_user:
        st.session_state.logado = True
        st.session_state.user_cpf = saved_user
        st.session_state.user_nome = cookie_manager.get(cookie="user_nome")
        st.session_state.user_tipo = cookie_manager.get(cookie="user_tipo")
    else:
        st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = False, "", ""

def logout():
    cookie_manager.delete("user_cpf")
    st.session_state.logado = False
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        tp = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("Finalizar Cadastro"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 2.0}]).execute()
            st.success("✅ Cadastrado!")

    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tl")
        lc, ls = st.text_input("CPF", key="lc"), st.text_input("Senha", type="password", key="ls")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = True, u['nome'], tl
                # SALVA NOS COOKIES (Expira em 1 dia)
                cookie_manager.set("user_cpf", lc)
                cookie_manager.set("user_nome", u['nome'])
                cookie_manager.set("user_tipo", tl)
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.button("Sair/Logout", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_geral')

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista...")
                st.button("🔄 Atualizar")
            else:
                st.success(f"✅ Motorista {c.get('motorista_nome')} aceitou!")
                st.metric("VALOR", f"R$ {c.get('valor_total', 0):.2f}")
        else:
            orig, dest = st.text_input("🏠 Origem"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando", "lat_origem": lat_p, "lon_origem": lon_p}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        # Busca o Preço/KM do motorista logado
        p_mot = conn.table("usuarios").select("preco_km").eq("nome", st.session_state.user_nome).execute()
        taxa_km = p_mot.data[0]['preco_km'] if p_mot.data else 2.0
        
        st.subheader(f"Sua Tarifa: R$ {taxa_km:.2f}/km")
        res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        for r in res_c.data:
            with st.container(border=True):
                # CÁLCULO DE PREÇO DINÂMICO
                dist_km = 0.0
                if loc and r.get('lat_origem'):
                    dist_km = geodesic((loc['coords']['latitude'], loc['coords']['longitude']), (r['lat_origem'], r['lon_origem'])).km
                
                # Se estiver muito perto ou sem GPS, assume 2.5km de base para o preço variar
                dist_calculada = dist_km if dist_km > 0.3 else 3.5 
                valor_final = 5.0 + (dist_calculada * 1.4 * taxa_km) # 1.4x para simular curvas das ruas
                
                st.write(f"👤 **{r['passageiro']}** | 💰 Ganho: **R$ {valor_final:.2f}**")
                if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                    conn.table("corridas").update({"status": "Em curso", "motorista_nome": st.session_state.user_nome, "valor_total": valor_final}).eq("id", r['id']).execute()
                    st.rerun()
