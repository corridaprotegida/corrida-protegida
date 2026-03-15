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
                st.warning("⏳ Buscando motorista...")
                st.button("🔄 Atualizar Status")
            elif c['status'] == "Em curso":
                st.success(f"✅ Motorista **{c.get('motorista_nome')}** a caminho!")
                val = c.get('valor_total', 0)
                st.metric("Valor Sugerido (Pague ao chegar)", f"R$ {val:.2f}")
                st.info(f"⏱️ Previsão: {c.get('tempo_chegada', 'A caminho')}")
                st.write("⚠️ Aguarde o motorista finalizar a viagem no app dele.")
        else:
            orig, dest = st.text_input("🏠 Origem"), st.text_input("🏁 Destino")
            if st.button("CHAMAR AGORA"):
                lat_p, lon_p = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando", "lat_origem": lat_p, "lon_origem": lon_p}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        # Aba de Configuração de Preço
        tab_corridas, tab_config = st.tabs(["🛣️ Corridas", "⚙️ Minha Tarifa"])
        
        with tab_config:
            st.subheader("Configurar Preço por KM")
            # Busca preço atual do banco
            meu_perfil = conn.table("usuarios").select("preco_km").eq("nome", st.session_state.user_nome).execute()
            preco_atual = meu_perfil.data[0]['preco_km'] if meu_perfil.data else 2.0
            
            novo_preco = st.number_input("Quanto você quer cobrar por KM?", min_value=1.0, max_value=10.0, value=float(preco_atual), step=0.10)
            
            if st.button("Salvar Tarifa"):
                if novo_preco > 7.0:
                    st.error("❌ Limite Máximo atingido! O valor máximo permitido é R$ 7,00 por KM.")
                else:
                    conn.table("usuarios").update({"preco_km": novo_preco}).eq("nome", st.session_state.user_nome).execute()
                    st.success(f"✅ Tarifa de R$ {novo_preco:.2f}/km salva com sucesso!")

        with tab_corridas:
            # Verifica se já está em uma corrida
            minha_ativa = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Em curso").execute()
            
            if minha_ativa.data:
                ma = minha_ativa.data[0]
                st.success(f"🏁 Você está em viagem com **{ma['passageiro']}**")
                st.info(f"Destino: {ma['ponto_destino']}")
                if st.button("🚩 FINALIZAR VIAGEM"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", ma['id']).execute()
                    st.balloons()
                    st.rerun()
            else:
                res_c = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
                if not res_c.data:
                    st.info("Buscando passageiros..."); st.button("🔄 Atualizar")
                for r in res_c.data:
                    with st.container(border=True):
                        st.write(f"👤 **{r['passageiro']}** | Destino: {r['ponto_destino']}")
                        
                        dist, tempo, valor = 0.0, "5-10 min", 0.0
                        if loc and r.get('lat_origem'):
                            p_mot = (loc['coords']['latitude'], loc['coords']['longitude'])
                            p_psg = (r['lat_origem'], r['lon_origem'])
                            dist = geodesic(p_mot, p_psg).km
                            tempo = f"{int(dist * 4) + 2} min"
                            # Calcula valor com base no PREÇO KM do motorista logado
                            valor = dist * novo_preco
                            st.write(f"📏 Distância: {dist:.2f} km | 💰 Valor Sugerido: **R$ {valor:.2f}**")

                        if st.button(f"✅ Aceitar Corrida #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({
                                "status": "Em curso", "motorista_nome": st.session_state.user_nome,
                                "tempo_chegada": tempo, "valor_total": valor
                            }).eq("id", r['id']).execute()
                            st.rerun()
