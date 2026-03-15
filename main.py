import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import pandas as pd
import urllib.parse
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

if "logado" not in st.session_state:
    st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = False, "", ""

def logout():
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
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s}]).execute()
            st.success("✅ Cadastrado!")
    with t1:
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
    
    # Captura GPS em tempo real (necessário para cálculo de distância)
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_geral')

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista... O GPS dele será calculado ao aceitar.")
                st.button("🔄 Atualizar Status")
            else:
                st.success(f"✅ Motorista **{c.get('motorista_nome')}** a caminho!")
                dist = c.get('distancia_km')
                if dist:
                    tempo = int(dist * 4) # Estimativa 4 min por KM
                    st.metric("Distância do Motorista", f"{dist:.2f} km", f"Chegada em ~{tempo} min")
                if st.button("🏁 Finalizar (Cheguei)"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
        else:
            orig, dest = st.text_input("🏠 Onde você está?"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                # Se o GPS do passageiro estiver ativo, salvamos as coordenadas
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando", "lat_origem": lat_p, "lon_origem": lon_p}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        if not res_c.data:
            st.info("Buscando passageiros..."); st.button("🔄 Atualizar")
        else:
            for r in res_c.data:
                with st.container(border=True):
                    st.write(f"👤 **{r['passageiro']}**")
                    st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                    
                    # Cálculo de distância se ambos tiverem GPS
                    dist_calculada = None
                    if loc and r.get('lat_origem'):
                        p_mot = (loc['coords']['latitude'], loc['coords']['longitude'])
                        p_psg = (r['lat_origem'], r['lon_origem'])
                        dist_calculada = geodesic(p_mot, p_psg).km
                        st.info(f"📏 Você está a {dist_calculada:.2f} km deste passageiro.")

                    # Link do Mapa Estático
                    end_b = urllib.parse.quote(r['ponto_origem'])
                    st.image(f"https://static-maps.yandex.ru{end_b}", caption="Localização aproximada")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            lat_m, lon_m = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                            conn.table("corridas").update({
                                "status": "Em curso", 
                                "motorista_nome": st.session_state.user_nome,
                                "lat_motorista": lat_m, "lon_motorista": lon_m,
                                "distancia_km": dist_calculada
                            }).eq("id", r['id']).execute()
                            st.success("Aceito!"); st.balloons(); time.sleep(1); st.rerun()
                    with col2:
                        # Deep Links para os Apps
                        st.markdown(f'<a href="waze://?q={end_b}&navigate=yes"><button style="background:#33ccff;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;cursor:pointer;">🚗 Abrir WAZE</button></a>', unsafe_allow_html=True)
