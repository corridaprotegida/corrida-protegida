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
    
    # Captura GPS (Ambos precisam permitir no navegador)
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_geral')

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista... Fique na página.")
                st.button("🔄 Atualizar Status")
            elif c['status'] == "Em curso":
                st.success(f"✅ O motorista **{c.get('motorista_nome')}** aceitou sua corrida!")
                tempo = c.get('tempo_chegada', "A caminho")
                st.info(f"⏱️ Previsão de chegada: **{tempo}**")
                
                if st.button("🏁 Finalizar (Cheguei)"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
        else:
            orig, dest = st.text_input("🏠 Onde você está? (Endereço)"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                # Salva Lat/Lon do passageiro se o GPS permitir
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{
                    "passageiro": st.session_state.user_nome, 
                    "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando",
                    "lat_origem": lat_p, "lon_origem": lon_p
                }]).execute()
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
                    
                    # Cálculo de distância se houver GPS de ambos
                    tempo_estimado = "5 a 10 min"
                    if loc and r.get('lat_origem'):
                        p_mot = (loc['coords']['latitude'], loc['coords']['longitude'])
                        p_psg = (r['lat_origem'], r['lon_origem'])
                        dist = geodesic(p_mot, p_psg).km
                        tempo_estimado = f"{int(dist * 4) + 2} min"
                        st.info(f"📏 Você está a {dist:.2f} km do passageiro (~{tempo_estimado})")

                    # Mapa estático
                    end_b = urllib.parse.quote(r['ponto_origem'])
                    st.image(f"https://static-maps.yandex.ru{end_b}")

                    if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                        conn.table("corridas").update({
                            "status": "Em curso", 
                            "motorista_nome": st.session_state.user_nome,
                            "tempo_chegada": tempo_estimado
                        }).eq("id", r['id']).execute()
                        st.success("Corrida Aceita! O passageiro foi avisado."); st.balloons(); time.sleep(1); st.rerun()
                    
                    # Deep Links para Apps
                    st.markdown(f'<a href="waze://?q={end_b}&navigate=yes"><button style="background:#33ccff;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;cursor:pointer;">🚗 Abrir WAZE</button></a>', unsafe_allow_html=True)
