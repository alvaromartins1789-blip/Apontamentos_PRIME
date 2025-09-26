# streamlit_app.py (versão estilizada atualizada — inicia em branco e pede seleção)
from pathlib import Path
from datetime import date
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Apontamentos - PRIME",
    page_icon="./images/simbolo-favico.png",
    layout="wide"
)

# ====== CSS ======
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { width: 520px; }
    .sidebar-project-list { max-height: 56vh; overflow: auto; padding-right: 6px; }
    .proj-btn { display:block; text-align:left; padding:6px 8px; border-radius:6px; margin-bottom:4px; background:transparent; border:none; }
    .proj-btn:hover { background-color:#f2f4f7; }
    .proj-selected { font-weight:700; color:#0f172a; }
    hr.sidebar-hr { border:none; border-top:1px solid #e6e9ee; margin:6px 0; }

    .metric-card-large {
        padding: 1.0rem 1.25rem;
        border-radius: 14px;
        background: #ffffff;
        box-shadow: 0 6px 18px rgba(15,23,42,0.06);
        text-align: center;
        display: inline-block;
        width: 100%;
        min-height: 78px;
    }
    .metric-card-large h3 { margin:0 0 6px 0; font-size:16px; color:#0f172a; }
    .metric-card-large .value { font-size:20px; font-weight:700; margin:0; color:#0f172a; }
    .metric-card-large .sub { margin-top:6px; font-size:12px; color:#667085; }

    .no-select { -webkit-user-select:none; -moz-user-select:none; -ms-user-select:none; user-select:none; }

    @media (max-width: 600px) {
        .metric-card-large { padding:0.8rem; min-height:68px; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ====== CONFIGURAÇÃO ======
DATA_DIR = Path("./data")
BUDGET_PER_PROJECT = 100_000.0

hourly_rates = {
    "WERLITON GOMES BARROSO": 75.00,
    "TANIA DE ARRUDA FERNANDES": 43.54,
    "TALES FERNANDO SEGUNDO": 85.00,
    "RAFAEL JEFERSON GIARETTA": 20.76
}

# ====== FUNÇÕES ======
def find_csv_files(data_dir: Path):
    if not data_dir.exists():
        return []
    return sorted([p for p in data_dir.glob("*.csv")])

def safe_parse_datetime(col_series):
    return pd.to_datetime(col_series, dayfirst=True, errors="coerce")

def load_project_csv(path: Path):
    df = pd.read_csv(path, sep=';')
    df.columns = [c.strip() for c in df.columns]

    if "Data" in df.columns:
        df["Data_parsed"] = safe_parse_datetime(df["Data"])
    elif "data" in df.columns:
        df["Data_parsed"] = safe_parse_datetime(df["data"])
    else:
        df["Data_parsed"] = pd.NaT

    if "Horas" in df.columns:
        horas_td = pd.to_timedelta(df["Horas"].astype(str), errors='coerce')
        df["Horas_num"] = horas_td.dt.total_seconds() / 3600.0
        numeric_hours = pd.to_numeric(df["Horas"].astype(str).str.replace(",", "."), errors="coerce")
        df["Horas_num"] = df["Horas_num"].fillna(numeric_hours)
    else:
        df["Horas_num"] = np.nan

    if ("Horário de início" in df.columns or "Horario de inicio" in df.columns) and \
       ("Horário de fim" in df.columns or "Horario de fim" in df.columns):
        col_start = "Horário de início" if "Horário de início" in df.columns else "Horario de inicio"
        col_end = "Horário de fim" if "Horário de fim" in df.columns else "Horario de fim"
        start_parsed = pd.to_datetime(df['Data_parsed'].dt.strftime('%Y-%m-%d') + ' ' + df[col_start].astype(str), errors='coerce')
        end_parsed = pd.to_datetime(df['Data_parsed'].dt.strftime('%Y-%m-%d') + ' ' + df[col_end].astype(str), errors='coerce')
        duration_hours = (end_parsed - start_parsed).dt.total_seconds() / 3600.0
        df["Horas_num"] = df["Horas_num"].fillna(duration_hours)

    usuario_col = None
    for candidate in ["Usuário", "Usuario", "usuario", "usuário"]:
        if candidate in df.columns:
            usuario_col = candidate
            break
    if usuario_col:
        df["Usuario_norm"] = df[usuario_col].astype(str).str.strip().str.upper()
    else:
        df["Usuario_norm"] = "DESCONHECIDO"

    if "Projeto" in df.columns:
        df["Projeto_name"] = df["Projeto"].astype(str).str.strip()
    else:
        df["Projeto_name"] = path.stem

    df["Data_date"] = df["Data_parsed"].dt.date
    df = df.dropna(subset=["Data_date"], how="all").copy()
    df["Horas_num"] = df["Horas_num"].fillna(0.0)
    return df

def group_month_str(d: date):
    return d.strftime("%Y-%m")

def get_available_months_for_df(df: pd.DataFrame):
    if df.empty:
        return []
    today = date.today()
    months = df["Data_date"].dropna().apply(group_month_str).unique().tolist()
    months = [m for m in months if m <= today.strftime("%Y-%m")]
    return sorted(months)

def compute_costs_for_df(df: pd.DataFrame, rates: dict):
    df = df.copy()
    df["rate"] = df["Usuario_norm"].map(rates).fillna(0.0)
    df["Custo"] = df["Horas_num"] * df["rate"]
    return df

def summarize_project(df: pd.DataFrame, rates: dict):
    dfc = compute_costs_for_df(df, rates)
    total_cost = dfc["Custo"].sum()
    hours_by_user_total = dfc.groupby("Usuario_norm")["Horas_num"].sum().sort_values(ascending=False)
    dfc["month"] = dfc["Data_date"].apply(group_month_str)
    hours_by_month = dfc.groupby("month")["Horas_num"].sum().sort_index()
    cost_by_month = dfc.groupby("month")["Custo"].sum().sort_index()
    return {
        "total_cost": total_cost,
        "hours_by_user_total": hours_by_user_total,
        "hours_by_month": hours_by_month,
        "cost_by_month": cost_by_month,
        "dfc": dfc
    }

def project_budget_remaining(total_cost):
    return BUDGET_PER_PROJECT - total_cost

def project_month_projection(dfc_month: pd.DataFrame, month_str: str):
    if dfc_month.empty:
        return 0.0
    return dfc_month["Custo"].sum()

def placeholder_metric(titulo, sub="Selecione um projeto e um período."):
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>{titulo}</h3>
            <p class="value">--/--</p>
            <div class="sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ====== Carregar projetos ======
csv_files = find_csv_files(DATA_DIR)
if not csv_files:
    st.warning(f"Nenhum CSV encontrado em {DATA_DIR.resolve()}. Coloque seus arquivos .csv na pasta 'data/'.")
    st.stop()

project_name_to_path_map = {}
for p in csv_files:
    try:
        df_temp = pd.read_csv(p, sep=';', usecols=['Projeto'])
        if not df_temp['Projeto'].dropna().empty:
            project_name = df_temp['Projeto'].dropna().iloc[0].strip()
            project_name_to_path_map[project_name] = p
    except Exception as e:
        st.error(f"Erro ao processar o arquivo {p.name}: {e}")

project_names = sorted(list(project_name_to_path_map.keys()))

# ====== Sidebar ======
st.sidebar.header("Filtros")

search_term = st.sidebar.text_input("Pesquisar projeto", value="", placeholder="Digite parte do nome (ex: GenAI)")

if st.sidebar.button("Limpar pesquisa"):
    if "sidebar_search" in st.session_state:
        st.session_state["sidebar_search"] = ""
    search_term = ""

term = (search_term or "").strip().lower()
filtered = [p for p in project_names if term in p.lower()] if term else project_names.copy()

if "selected_project_click" not in st.session_state:
    st.session_state["selected_project_click"] = None

# Botão opcional "Todos os projetos" (não é padrão)
if st.sidebar.button("Todos os projetos"):
    st.session_state["selected_project_click"] = "Todos os projetos"

st.sidebar.markdown(f"**{len(filtered)}** projeto(s) encontrado(s)")

st.sidebar.markdown('<div class="sidebar-project-list">', unsafe_allow_html=True)
for i, p in enumerate(filtered):
    if st.sidebar.button(p, key=f"proj_btn_{i}"):
        st.session_state["selected_project_click"] = p
    st.sidebar.markdown('<hr class="sidebar-hr">', unsafe_allow_html=True)
st.sidebar.markdown('</div>', unsafe_allow_html=True)

st.sidebar.markdown("**Selecionado:**")
sel_label = st.session_state["selected_project_click"] or "— selecione um projeto —"
st.sidebar.markdown(f"> {sel_label}")

selected_project = st.session_state["selected_project_click"]

# ====== Título + Logo ======
header_col1, header_col2 = st.columns([8, 1])
with header_col1:
    if not selected_project:
        st.title("Painel de Custos — selecione um projeto")
    elif selected_project == "Todos os projetos":
        st.title("Painel de Custos - Todos os Projetos")
    else:
        st.title(f"Painel de Custos - {selected_project}")
with header_col2:
    st.image("./images/cropped-ico_primecontrol-378x378.png", width=80)

# ====== Se não escolheu projeto: placeholders e stop ======
if not selected_project:
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: placeholder_metric("Custo total do projeto")
    with col2: placeholder_metric("Horas Apontadas (Período Selecionado)")
    with col3: placeholder_metric("Custo (Período Selecionado)")
    with col4: placeholder_metric("Orçamento (limite)")
    with col5: placeholder_metric("Restante a gastar")
    st.info("Escolha um projeto na barra lateral para liberar a seleção de período.")
    st.stop()

# ====== Carregar dados do projeto selecionado ======
if selected_project == "Todos os projetos":
    dfs = [load_project_csv(p) for p in project_name_to_path_map.values()]
    display_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
else:
    path = project_name_to_path_map[selected_project]
    display_df = load_project_csv(path)

if display_df.empty:
    st.info("Não há dados para o projeto/seleção escolhida.")
    st.stop()

display_df = compute_costs_for_df(display_df, hourly_rates)
available_months_sorted = get_available_months_for_df(display_df)

# ====== Filtro de meses ======
st.sidebar.markdown("### Período")
if not available_months_sorted:
    st.info("Não há meses disponíveis para este projeto.")
    st.stop()

select_all_months = st.sidebar.checkbox("Selecionar todos os meses", value=False)
if select_all_months:
    selected_months = available_months_sorted.copy()
else:
    selected_months = st.sidebar.multiselect(
        "Selecione um ou mais meses",
        options=available_months_sorted,
        default=[],
        help="Obrigatório: escolha ao menos um mês.",
        placeholder="Escolha os meses (ex.: 2025-08, 2025-09)"  # <- texto em PT
    )

# Se não selecionou mês: placeholders e stop
if not selected_months:
    st.subheader("Horas e custo — selecione um período")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: placeholder_metric("Custo total do projeto", "Selecione um ou mais meses.")
    with col2: placeholder_metric("Horas Apontadas (Período Selecionado)", "Selecione um ou mais meses.")
    with col3: placeholder_metric("Custo (Período Selecionado)", "Selecione um ou mais meses.")
    with col4: placeholder_metric("Orçamento (limite)", "Selecione um ou mais meses.")
    with col5: placeholder_metric("Restante a gastar", "Selecione um ou mais meses.")
    st.stop()

# ====== Dados filtrados e título ======
df_filtered = display_df[display_df["Data_date"].apply(group_month_str).isin(selected_months)].copy()
subtitle_suffix = ", ".join(selected_months)
st.subheader(f"Horas e custo — {subtitle_suffix}")

# ====== Resumo e métricas ======
summary = summarize_project(display_df, hourly_rates)
total_cost_project = summary["total_cost"]
budget_remaining = project_budget_remaining(total_cost_project)

cost_selected_period = df_filtered["Custo"].sum()
hours_selected_period = df_filtered['Horas_num'].sum()

# ====== Cartões ======
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>Custo total do projeto</h3>
            <p class="value">R$ {total_cost_project:,.2f}</p>
            <div class="sub">Somatório de custos de todo o projeto</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>Horas Apontadas (Período Selecionado)</h3>
            <p class="value">{hours_selected_period:.2f} h</p>
            <div class="sub">Horas registradas no período selecionado</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>Custo (Período Selecionado)</h3>
            <p class="value">R$ {cost_selected_period:,.2f}</p>
            <div class="sub">Custo do período selecionado</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col4:
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>Orçamento (limite)</h3>
            <p class="value">R$ {BUDGET_PER_PROJECT:,.2f}</p>
            <div class="sub">Orçamento máximo previsto</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col5:
    st.markdown(
        f"""
        <div class="metric-card-large no-select">
            <h3>Restante a gastar</h3>
            <p class="value">R$ {budget_remaining:,.2f}</p>
            <div class="sub">Saldo disponível do orçamento</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ====== Custo real acumulado no mês vigente ======
today_key = date.today().strftime("%Y-%m")
real_cost = 0.0
if today_key in available_months_sorted:
    df_month = display_df[display_df["Data_date"].apply(group_month_str) == today_key]
    real_cost = project_month_projection(df_month, today_key)

st.markdown(
    f"""
    <div style="
        margin-top: 15px;
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        background: #f9fafb;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        display: inline-block;
    " class="no-select">
        <span style="font-weight:600; color:#0f172a;">Custo real acumulado no mês vigente ({today_key}):</span>
        <span style="font-weight:700; font-size:18px; margin-left:6px; color:#1d4ed8;">
            R$ {real_cost:,.2f}
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ====== Tabela por usuário ======
user_summary = df_filtered.groupby("Usuario_norm").agg(
    Horas_apontadas=("Horas_num", "sum"),
    Custo_total=("Custo", "sum"),
    Rate=("rate", "first")
).sort_values("Horas_apontadas", ascending=False)

df_table = user_summary.reset_index().rename(columns={
    "Usuario_norm": "Usuário",
    "Horas_apontadas": "Horas apontadas (h)",
    "Custo_total": "Custo total (R$)",
    "Rate": "Valor hora (R$)"
})

# Formatação numérica
df_table["Horas apontadas (h)"] = df_table["Horas apontadas (h)"].map(
    lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)
df_table["Custo total (R$)"] = df_table["Custo total (R$)"].map(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)
df_table["Valor hora (R$)"] = df_table["Valor hora (R$)"].map(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.markdown("###  Horas e custo detalhado por usuário")
st.dataframe(
    df_table.style
        .set_properties(**{"text-align": "center"})
        .set_table_styles([{"selector": "th", "props": [("background-color", "#f1f5f9"), ("color", "#0f172a"), ("font-weight", "600")]}])
        .highlight_max(subset=["Custo total (R$)"], color="#dbeafe")
        .highlight_min(subset=["Custo total (R$)"], color="#fef9c3"),
    use_container_width=True,
    hide_index=True
)

# ====== Gráfico auxiliar ======
if not summary["cost_by_month"].empty:
    # Prepara dados
    df_cost = summary["cost_by_month"].reset_index()  # colunas: month, Custo
    df_cost["Mes"] = df_cost["month"].astype(str)     # garante categoria, não data

    # Formata em PT-BR para o hover
    df_cost["Custo_fmt_pt"] = df_cost["Custo"].map(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    fig = px.bar(
        df_cost,
        x="Mes",
        y="Custo",
        title="Custo por mês",
        labels={"Mes": "Mês", "Custo": "R$"}
    )

    # X categórico (sem conversão pra data)
    fig.update_xaxes(type="category", title_text="Mês")
    fig.update_yaxes(title_text="R$")

    # Usa separadores PT-BR para qualquer número automático
    fig.update_layout(separators=",.")  # milhar=".", decimal=","

    # Hover 100% controlado com o valor já formatado
    fig.update_traces(
        customdata=df_cost[["Custo_fmt_pt"]],
        hovertemplate="Mês=%{x}<br>Custo=%{customdata[0]}<extra></extra>"
    )

    # (Opcional) mostrar rótulo em cima da barra também:
    # fig.update_traces(text=df_cost["Custo_fmt_pt"], textposition="outside")

    st.plotly_chart(fig, use_container_width=True)


st.info("Observação: Usuários não listados no mapa de salários terão rate = R$0,00.")
