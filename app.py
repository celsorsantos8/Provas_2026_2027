import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Gestão de Provas de Equipa", page_icon="🏃", layout="wide")

# Inicializar ligação ao Google Sheets configurada no Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# Colunas padrão
COLS_MAIN = ['Prova', 'Atleta', 'Distância', 'Data', 'Local', 'Prova de Equipa', 'Link']
COLS_PROVAS = ['PROVA', 'DATA', 'LOCAL', 'PROVA DE EQUIPA', 'Link']
COLS_INFO = ['Atleta', 'Distancia']

def carregar_aba(nome_aba, colunas_padrao):
    try:
        df = conn.read(worksheet=nome_aba, ttl=0)
        if df is not None and not df.empty:
            df.columns = df.columns.astype(str).str.strip()
            df = df.dropna(how='all')
            for col in colunas_padrao:
                if col not in df.columns:
                    df[col] = ""
            return df[colunas_padrao]
    except Exception:
        pass
    return pd.DataFrame(columns=colunas_padrao)

# Carregar dados diretamente da folha Google
df_main = carregar_aba("Main", COLS_MAIN)
df_provas = carregar_aba("Provas", COLS_PROVAS)
df_info = carregar_aba("Info", COLS_INFO)
df_historico = carregar_aba("Historico", COLS_MAIN)

# Sincronização automática para o Histórico (datas ultrapassadas)
def sync_expired_to_history(df_main, df_historico):
    if df_main.empty or 'Data' not in df_main.columns:
        return df_main, df_historico, 0

    # Carimbo temporal compatível a 100% com o pandas (meia-noite de hoje)
    today = pd.Timestamp.today().normalize()
    parsed_dates = pd.to_datetime(df_main['Data'], errors='coerce')

    expired_mask = (parsed_dates.notnull()) & (parsed_dates < today)
    expired_entries = df_main[expired_mask]

    if not expired_entries.empty:
        df_historico = pd.concat([df_historico, expired_entries], ignore_index=True)
        df_main = df_main[~expired_mask].reset_index(drop=True)

        # Atualizar no Google Sheets
        conn.update(worksheet="Main", data=df_main)
        conn.update(worksheet="Historico", data=df_historico)
        return df_main, df_historico, len(expired_entries)

    return df_main, df_historico, 0

df_main, df_historico, moved_count = sync_expired_to_history(df_main, df_historico)

# Listas auxiliares a partir da aba Info
atletas_list = sorted(df_info['Atleta'].dropna().astype(str).str.strip().unique().tolist()) if 'Atleta' in df_info.columns else []
distancias_list = sorted(df_info['Distancia'].dropna().astype(str).str.strip().unique().tolist()) if 'Distancia' in df_info.columns else []
provas_disponiveis = df_provas['PROVA'].dropna().unique().tolist() if ('PROVA' in df_provas.columns and not df_provas.empty) else []

# --- INTERFACE ---
st.title("🏃 Gestão de Provas de Equipa")

if moved_count > 0:
    st.info(f"ℹ️ {moved_count} prova(s) com data anterior a hoje foram transferidas para o Histórico.")

tab1, tab2, tab3 = st.tabs(["📅 Provas Agendadas", "📜 Histórico", "📋 Catálogo de Provas"])

# --- TAB 1: MAIN ---
with tab1:
    st.subheader("Inscrições Atuais da Equipa")

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        filtro_atleta = st.selectbox("Filtrar por Atleta:", ["Todos"] + atletas_list, key="filtro_main_atleta")
    with col_filtro2:
        provas_main_opts = sorted(df_main['Prova'].dropna().unique().tolist()) if ('Prova' in df_main.columns and not df_main.empty) else []
        filtro_prova = st.selectbox("Filtrar por Prova:", ["Todas"] + provas_main_opts, key="filtro_main_prova")

    df_view = df_main.copy()
    if filtro_atleta != "Todos" and 'Atleta' in df_view.columns:
        df_view = df_view[df_view['Atleta'] == filtro_atleta]
    if filtro_prova != "Todas" and 'Prova' in df_view.columns:
        df_view = df_view[df_view['Prova'] == filtro_prova]

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Inscrição / Informações")} if 'Link' in df_view.columns else None
    )

    st.markdown("---")
    st.subheader("➕ Registar Presença numa Prova")

    if not atletas_list or not provas_disponiveis:
        st.warning("Certifique-se de que a aba 'Info' tem atletas e a aba 'Provas' tem provas registadas.")
    else:
        with st.form("form_add_prova_atleta", clear_on_submit=True):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                atleta_sel = st.selectbox("Atleta:", atletas_list)
            with col_b:
                prova_sel = st.selectbox("Prova:", provas_disponiveis)
            with col_c:
                distancia_sel = st.selectbox("Tipo de Prova / Distância:", distancias_list if distancias_list else ["Geral"])

            info_prova = df_provas[df_provas['PROVA'] == prova_sel]
            if not info_prova.empty:
                p_data = str(info_prova.iloc[0].get('DATA', ''))
                p_local = str(info_prova.iloc[0].get('LOCAL', ''))
                p_equipa = str(info_prova.iloc[0].get('PROVA DE EQUIPA', 'Não'))
                p_link = str(info_prova.iloc[0].get('Link', ''))
            else:
                p_data, p_local, p_equipa, p_link = "", "", "Não", ""

            submeter = st.form_submit_button("Confirmar Inscrição")

            if submeter:
                data_prova_dt = pd.to_datetime(p_data, errors='coerce')
                nova_linha = pd.DataFrame([{
                    'Prova': prova_sel,
                    'Atleta': atleta_sel,
                    'Distância': distancia_sel,
                    'Data': p_data,
                    'Local': p_local,
                    'Prova de Equipa': p_equipa,
                    'Link': p_link
                }])

                if pd.notnull(data_prova_dt) and data_prova_dt < pd.Timestamp.today().normalize():
                    df_historico = pd.concat([df_historico, nova_linha], ignore_index=True)
                    conn.update(worksheet="Historico", data=df_historico)
                    st.warning("⚠️ Esta prova já passou, pelo que foi arquivada diretamente no Histórico.")
                else:
                    df_main = pd.concat([df_main, nova_linha], ignore_index=True)
                    conn.update(worksheet="Main", data=df_main)
                    st.success(f"✅ Inscrição de {atleta_sel} gravada com sucesso!")
                st.rerun()

# --- TAB 2: HISTÓRICO ---
with tab2:
    st.subheader("Registo Histórico de Provas Concluídas")

    if not df_historico.empty:
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            h_atleta = st.selectbox("Filtrar Histórico por Atleta:", ["Todos"] + atletas_list, key="hist_atleta")
        with col_h2:
            provas_hist = sorted(df_historico['Prova'].dropna().unique().tolist()) if 'Prova' in df_historico.columns else []
            h_prova = st.selectbox("Filtrar por Prova:", ["Todas"] + provas_hist, key="hist_prova")

        df_hist_view = df_historico.copy()
        if h_atleta != "Todos" and 'Atleta' in df_hist_view.columns:
            df_hist_view = df_hist_view[df_hist_view['Atleta'] == h_atleta]
        if h_prova != "Todas" and 'Prova' in df_hist_view.columns:
            df_hist_view = df_hist_view[df_hist_view['Prova'] == h_prova]

        st.dataframe(
            df_hist_view,
            use_container_width=True,
            hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link")} if 'Link' in df_hist_view.columns else None
        )
    else:
        st.info("Nenhuma prova registada no histórico.")

# --- TAB 3: CATÁLOGO DE PROVAS ---
with tab3:
    st.subheader("Provas Oficiais Disponíveis no Calendário")
    st.dataframe(
        df_provas,
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link Oficial")} if 'Link' in df_provas.columns else None
    )

    st.markdown("---")
    st.subheader("➕ Adicionar Nova Prova ao Calendário Geral")
    with st.form("form_nova_prova_catalogo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            n_nome = st.text_input("Nome da Prova:")
            n_data = st.date_input("Data da Prova:")
            n_local = st.text_input("Localidade:")
        with c2:
            n_equipa = st.selectbox("Conta como Prova de Equipa?", ["Não", "Sim"])
            n_link = st.text_input("Link da Inscrição / Organização:")

        submeter_prova = st.form_submit_button("Guardar Prova no Calendário")
        if submeter_prova:
            if n_nome.strip():
                nova_p = pd.DataFrame([{
                    'PROVA': n_nome.strip(),
                    'DATA': n_data.strftime("%Y-%m-%d"),
                    'LOCAL': n_local.strip(),
                    'PROVA DE EQUIPA': n_equipa,
                    'Link': n_link.strip()
                }])
                df_provas = pd.concat([df_provas, nova_p], ignore_index=True)
                conn.update(worksheet="Provas", data=df_provas)
                st.success(f"Prova '{n_nome}' adicionada ao catálogo com sucesso!")
                st.rerun()
            else:
                st.error("O nome da prova é obrigatório.")
