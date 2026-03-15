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
        pix = st.text_input("Sua Chave PIX (Se for motorista)")
        if st.button("Finalizar Cadastro"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix, "preco_km": 2.0}]).execute()
            st.success("✅ Cadastrado! Faça o login.")
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
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_geral')

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").order("id", desc=True).limit(1).execute()
        
        if res.data:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista... O valor aparecerá aqui.")
                st.button("🔄 Atualizar Status")
            elif c['status'] == "Em curso":
                st.success(f"✅ Motorista **{c.get('motorista_nome')}** aceitou!")
                val = c.get('valor_total', 0.0)
                st.metric("VALOR TOTAL", f"R$ {val:.2f}")
                
                # Busca a chave PIX do motorista que aceitou
                mot_info = conn.table("usuarios").select("chave_pix").eq("nome", c.get('motorista_nome')).execute()
                pix_mot = mot_info.data[0]['chave_pix'] if mot_info.data else "Combine no carro"
                st.info(f"💰 **Pague via PIX:** {pix_mot}")
                st.write("⚠️ O motorista encerrará a viagem ao chegar.")
        else:
            orig, dest = st.text_input("🏠 Onde você está?"), st.text_input("🏁 Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando", "lat_origem": lat_p, "lon_origem": lon_p}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        t_corr, t_conf = st.tabs(["🛣️ Corridas", "⚙️ Minha Tarifa"])
        perfil = conn.table("usuarios").select("*").eq("nome", st.session_state.user_nome).execute()
        taxa_km = perfil.data[0]['preco_km'] if perfil.data else 2.0

        with t_conf:
            st.subheader("Configurações de Ganho")
            n_pix = st.text_input("Sua Chave PIX", value=perfil.data[0].get('chave_pix', ''))
            n_p = st.number_input("Preço por KM (Máx R$ 7,00)", min_value=1.0, max_value=10.0, value=float(taxa_km), step=0.1)
            if st.button("Salvar Configurações"):
                if n_p > 7.0: st.error("❌ Limite de R$ 7,00 excedido!")
                else:
                    conn.table("usuarios").update({"preco_km": n_p, "chave_pix": n_pix}).eq("nome", st.session_state.user_nome).execute()
                    st.success("✅ Configurações salvas!")
                    st.rerun()

        with t_corr:
            ativa = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Em curso").execute()
            if ativa.data:
                viagem = ativa.data[0]
                st.info(f"Em curso com: {viagem['passageiro']}")
                if st.button("🚩 FINALIZAR CORRIDA E LIBERAR"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", viagem['id']).execute()
                    st.balloons(); st.rerun()
            else:
                disponiveis = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
                if not disponiveis.data: st.info("Buscando..."); st.button("🔄 Atualizar")
                for r in disponiveis.data:
                    with st.container(border=True):
                        dist_km = 0.0
                        if loc and r.get('lat_origem'):
                            p_m, p_p = (loc['coords']['latitude'], loc['coords']['longitude']), (r['lat_origem'], r['lon_origem'])
                            dist_km = geodesic(p_m, p_p).km
                        
                        # Simulação de trajeto (multiplica por 1.3 para ruas reais) + Taxa Base R$ 5,00
                        dist_calculada = dist_km if dist_km > 0.5 else 2.5 # Mínimo 2.5km se estiver perto
                        valor_final = 5.0 + (dist_calculada * 1.3 * taxa_km)
                        
                        st.write(f"👤 **{r['passageiro']}** | 💰 Ganho: **R$ {valor_final:.2f}**")
                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({"status": "Em curso", "motorista_nome": st.session_state.user_nome, "valor_total": valor_final}).eq("id", r['id']).execute()
                            st.rerun()
