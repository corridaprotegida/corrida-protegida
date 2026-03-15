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
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 2.0}]).execute()
            st.success("✅ Cadastrado!")
    with t1:
        tl = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tl")
        lc, ls = st.text_input("CPF", key="lc"), st.text_input("Senha", type="password", key="ls")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                st.session_state.logado, st.session_state.user_nome, st.session_state.user_tipo = True, r.data[0]['nome'], tl
                st.rerun()

# --- PAINEL LOGADO ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")
    
    # Captura GPS
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_geral')

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista... O valor será calculado ao aceitar.")
                st.button("🔄 Atualizar Status")
            elif c['status'] == "Em curso":
                st.success(f"✅ Motorista **{c.get('motorista_nome')}** aceitou!")
                valor_final = c.get('valor_total') or 0.0
                st.metric("VALOR A PAGAR", f"R$ {valor_final:.2f}", "Pague via PIX ao motorista")
                st.info(f"⏱️ Previsão: {c.get('tempo_chegada', 'A caminho')}")
        else:
            orig, dest = st.text_input("🏠 Origem"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando", "lat_origem": lat_p, "lon_origem": lon_p}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        t_corr, t_conf = st.tabs(["🛣️ Corridas", "⚙️ Configurar Tarifa"])
        
        # BUSCA PREÇO DO MOTORISTA
        perfil = conn.table("usuarios").select("preco_km").eq("nome", st.session_state.user_nome).execute()
        taxa_km = perfil.data[0]['preco_km'] if perfil.data else 2.0

        with t_conf:
            st.subheader("Sua Tarifa Atual")
            novo_p = st.number_input("Preço por KM (Máx R$ 7,00)", min_value=1.0, max_value=10.0, value=float(taxa_km), step=0.1)
            if st.button("Salvar Nova Tarifa"):
                if novo_p > 7.0:
                    st.error("❌ Erro: O valor máximo permitido é R$ 7,00/km.")
                else:
                    conn.table("usuarios").update({"preco_km": novo_p}).eq("nome", st.session_state.user_nome).execute()
                    st.success("✅ Tarifa atualizada!")
                    time.sleep(1); st.rerun()

        with t_corr:
            # Verifica se já está em viagem
            ativa = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Em curso").execute()
            if ativa.data:
                viagem = ativa.data[0]
                st.info(f"Em curso com: {viagem['passageiro']}")
                if st.button("🚩 FINALIZAR CORRIDA"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", viagem['id']).execute()
                    st.balloons(); st.rerun()
            else:
                disponiveis = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
                if not disponiveis.data:
                    st.write("Nenhuma corrida... Aguarde."); st.button("🔄 Atualizar")
                for r in disponiveis.data:
                    with st.container(border=True):
                        # CÁLCULO DE DISTÂNCIA E VALOR
                        dist_real = 0.0
                        if loc and r.get('lat_origem'):
                            p_mot = (loc['coords']['latitude'], loc['coords']['longitude'])
                            p_psg = (r['lat_origem'], r['lon_origem'])
                            dist_real = geodesic(p_mot, p_psg).km
                        
                        # LOGICA DE SEGURANÇA: Se a distância for 0 (GPS falhou), assume 3km de base
                        dist_final = dist_real if dist_real > 0.1 else 3.0
                        valor_sugerido = 5.0 + (dist_final * taxa_km) # R$ 5,00 fixo + KM
                        tempo_est = f"{int(dist_final * 4) + 2} min"

                        st.write(f"👤 **{r['passageiro']}** | 📍 {r['ponto_origem']}")
                        st.write(f"💰 Valor: **R$ {valor_sugerido:.2f}** (Base: {dist_final:.1f}km)")

                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({
                                "status": "Em curso", "motorista_nome": st.session_state.user_nome,
                                "tempo_chegada": tempo_est, "valor_total": valor_sugerido
                            }).eq("id", r['id']).execute()
                            st.rerun()
