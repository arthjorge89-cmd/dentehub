import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

# Configurações e Constantes (equivalentes às do JS)
DENTISTAS = {
    'h': 'Dra. Helena Aguiar',
    'r': 'Dr. Rafael Moura',
    'l': 'Dra. Letícia Campos'
}

ENDERECO = 'Av. Conselheiro Aguiar, 2333, sala 1204 – Boa Viagem, Recife – PE'
SENHA_ADMIN = 'admin123'

def proximo_dia_util(data_base: datetime) -> datetime:
    while data_base.weekday() == 6:  # 6 = Domingo em Python
        data_base += timedelta(days=1)
    return data_base

# Banco de dados em memória inicializado com os dados de exemplo
def inicializar_dados():
    hoje = proximo_dia_util(datetime.now())
    amanha = proximo_dia_util(hoje + timedelta(days=1))
    return [
        {
            'id': '#DH-2026-4821',
            'nome': 'Mariana Souza',
            'tel': '(81) 99812-3456',
            'esp': 'Clareamento',
            'dent': 'h',
            'data': hoje.strftime('%Y-%m-%d'),
            'hora': '09:00',
            'conv': 'Particular',
            'status': 'confirmado'
        },
        {
            'id': '#DH-2026-3307',
            'nome': 'Carlos Eduardo Lima',
            'tel': '(81) 99644-7821',
            'esp': 'Ortodontia',
            'dent': 'r',
            'data': hoje.strftime('%Y-%m-%d'),
            'hora': '10:30',
            'conv': 'OdontoPrev',
            'status': 'pendente'
        },
        {
            'id': '#DH-2026-7215',
            'nome': 'Patrícia Lemos',
            'tel': '(81) 98733-0912',
            'esp': 'Odontopediatria',
            'dent': 'l',
            'data': amanha.strftime('%Y-%m-%d'),
            'hora': '14:00',
            'conv': 'Bradesco Dental',
            'status': 'pendente'
        }
    ]

agendamentos = inicializar_dados()

# --- FUNÇÕES DE REGRA DE NEGÓCIO EM PYTHON ---

def listar_horarios_dia(data_str: str) -> list:
    dt = datetime.strptime(data_str, '%Y-%m-%d')
    dia_semana = dt.weekday()  # 0=Seg ... 5=Sáb, 6=Dom
    if dia_semana == 6:
        return []
    
    fim_minutos = 690 if dia_semana == 5 else 1110  # Sáb até 11:30, Seg-Sex até 18:30
    horarios = []
    for m in range(480, fim_minutos + 1, 30):  # Começa às 08:00 (480 min)
        horarios.append(f"{m // 60:02d}:{m % 60:02d}")
    return horarios

def dentistas_livres(data_str: str, hora_str: str, pool_dentistas: list) -> list:
    ocupados = {
        a['dent'] for a in agendamentos
        if a['data'] == data_str and a['hora'] == hora_str and a['status'] != 'cancelado'
    }
    return [d for d in pool_dentistas if d not in ocupados]

# --- ROTAS DA API (BACKEND) ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/slots')
def api_slots():
    data_str = request.args.get('data', '')
    dent_pref = request.args.get('dent', '')
    
    if not data_str:
        return jsonify({'erro': 'Escolha uma data.', 'slots': []})
    
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    if data_str < hoje_str:
        return jsonify({'erro': 'Essa data já passou.', 'slots': []})
        
    dt = datetime.strptime(data_str, '%Y-%m-%d')
    if dt.weekday() == 6:
        return jsonify({'erro': 'Não atendemos aos domingos.', 'slots': []})

    pool = [dent_pref] if dent_pref in DENTISTAS else list(DENTISTAS.keys())
    agora = datetime.now()
    minuto_atual = agora.hour * 60 + agora.minute
    eh_hoje = (data_str == hoje_str)

    slots = []
    for h in listar_horarios_dia(data_str):
        hh, mm = map(int, h.split(':'))
        passou_hora = eh_hoje and (hh * 60 + mm <= minuto_atual)
        disponivel = (not passou_hora) and len(dentistas_livres(data_str, h, pool)) > 0
        slots.append({'hora': h, 'disponivel': disponivel})

    return jsonify({'erro': '', 'slots': slots})

@app.route('/api/agendar', methods=['POST'])
def api_agendar():
    dados = request.json
    nome = ' '.join(dados.get('nome', '').split())
    tel = dados.get('tel', '')
    esp = dados.get('esp', '')
    dent_pref = dados.get('dent', '')
    data_str = dados.get('data', '')
    hora = dados.get('hora', '')
    conv = dados.get('conv', 'Particular')

    pool = [dent_pref] if dent_pref in DENTISTAS else list(DENTISTAS.keys())
    livres = dentistas_livres(data_str, hora, pool)

    if not livres:
        return jsonify({'ok': False, 'erro': 'Esse horário acabou de ser ocupado. Escolha outro.'}), 409

    # Gera protocolo único
    ano = datetime.now().year
    ids_existentes = {a['id'] for a in agendamentos}
    while True:
        novo_id = f"#DH-{ano}-{random.randint(1000, 9999)}"
        if novo_id not in ids_existentes:
            break

    novo_agendamento = {
        'id': novo_id,
        'nome': nome,
        'tel': tel,
        'esp': esp,
        'dent': livres[0],
        'data': data_str,
        'hora': hora,
        'conv': conv,
        'status': 'pendente'
    }
    agendamentos.append(novo_agendamento)
    return jsonify({'ok': True, 'agendamento': novo_agendamento})

@app.route('/api/buscar')
def api_buscar():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    
    digitos = ''.join(filter(str.isdigit, q))
    proto = q.upper().replace('#', '')

    resultados = [
        a for a in agendamentos
        if a['id'].replace('#', '') == proto or
        (len(digitos) >= 8 and ''.join(filter(str.isdigit, a['tel'])).endswith(digitos))
    ]
    return jsonify(resultados)

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    senha = request.json.get('senha', '')
    if senha == SENHA_ADMIN:
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'erro': 'Senha incorreta.'}), 401

@app.route('/api/admin/lista')
def api_admin_lista():
    filtro_data = request.args.get('data', '')
    filtro_dent = request.args.get('dent', '')
    hoje_str = datetime.now().strftime('%Y-%m-%d')

    stats = {
        'hoje': sum(1 for a in agendamentos if a['data'] == hoje_str and a['status'] != 'cancelado'),
        'pendentes': sum(1 for a in agendamentos if a['status'] == 'pendente'),
        'confirmados': sum(1 for a in agendamentos if a['status'] == 'confirmado'),
    }

    filtrados = [
        a for a in agendamentos
        if (not filtro_data or a['data'] == filtro_data) and
           (not filtro_dent or a['dent'] == filtro_dent)
    ]
    filtrados.sort(key=lambda x: (x['data'], x['hora']))
    return jsonify({'stats': stats, 'lista': filtrados})

@app.route('/api/agendamento/acao', methods=['POST'])
def api_acao():
    global agendamentos
    dados = request.json
    ag_id = dados.get('id')
    acao = dados.get('acao')

    if acao == 'del':
        agendamentos = [a for a in agendamentos if a['id'] != ag_id]
        return jsonify({'ok': True})

    for a in agendamentos:
        if a['id'] == ag_id:
            a['status'] = acao
            return jsonify({'ok': True})

    return jsonify({'ok': False}), 404

@app.route('/api/ics/<path:ag_id>')
def api_ics(ag_id):
    ag_id_fmt = f"#{ag_id.lstrip('#')}"
    ag = next((a for a in agendamentos if a['id'] == ag_id_fmt), None)
    if not ag:
        return "Não encontrado", 404

    inicio = datetime.strptime(f"{ag['data']} {ag['hora']}", "%Y-%m-%d %H:%M")
    fim = inicio + timedelta(minutes=30)
    agora_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    ics_conteudo = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DenteHub//PT-BR",
        "BEGIN:VEVENT",
        f"UID:{ag['id'].replace('#', '')}@dentehub",
        f"DTSTAMP:{agora_utc}",
        f"DTSTART:{inicio.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{fim.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:Consulta DenteHub - {ag['esp']}",
        f"LOCATION:{ENDERECO.replace(',', '\\,')}",
        f"DESCRIPTION:Dentista: {DENTISTAS[ag['dent']]}\\nProtocolo: {ag['id']}",
        "END:VEVENT",
        "END:VCALENDAR"
    ])

    return Response(
        ics_conteudo,
        mimetype="text/calendar",
        headers={"Content-disposition": "attachment; filename=consulta-dentehub.ics"}
    )

# --- TEMPLATE FRONTEND INTEGRADO À API PYTHON ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DenteHub – Clínica Odontológica</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#F6FBFB;--surface:#fff;--ink:#0C2B3A;--muted:#4D6672;--teal:#0E7C86;--aqua:#D6EEF0;--cta:#FF6B57;--ctaink:#fff;--line:#CFE3E6;--on:#fff;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0A1C25;--surface:#10303D;--ink:#EAF6F7;--muted:#9CBBC4;--teal:#4FD1D9;--aqua:#14404E;--line:#1E4756;--on:#062A30}}
:root[data-theme="dark"]{--bg:#0A1C25;--surface:#10303D;--ink:#EAF6F7;--muted:#9CBBC4;--teal:#4FD1D9;--aqua:#14404E;--line:#1E4756;--on:#062A30}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:70px}
body{margin:0;background:var(--bg);color:var(--ink);font:400 17px/1.6 'DM Sans',system-ui,sans-serif}
h1,h2,h3{font-family:'Bricolage Grotesque',system-ui,sans-serif;line-height:1.1;margin:0}
a{color:inherit}small{color:var(--muted)}.wrap{max-width:1080px;margin:0 auto;padding:0 22px}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
header .wrap{display:flex;align-items:center;gap:14px;height:64px}
.logo{font:800 22px 'Bricolage Grotesque',sans-serif;text-decoration:none;color:var(--teal)}
nav{display:flex;align-items:center;margin-left:auto}
nav a,.lnk{margin-left:22px;text-decoration:none;font:500 17px 'DM Sans',sans-serif;color:var(--muted);background:none;border:0;cursor:pointer;padding:0}
nav a:hover,.lnk:hover{color:var(--ink)}
.ib{width:40px;height:40px;border-radius:50%;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer;font-size:18px;display:grid;place-items:center}
.burger{display:none}
.btn{display:inline-block;background:var(--cta);color:var(--ctaink);font-weight:700;padding:14px 26px;border-radius:999px;text-decoration:none;border:0;cursor:pointer;font-size:16px;font-family:inherit}
.btn:hover{filter:brightness(1.07)}.btn.ghost{background:transparent;color:var(--ink);border:2px solid var(--line)}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--teal);outline-offset:3px}
.hero{padding:64px 0 72px}.hero .wrap{display:grid;grid-template-columns:1.1fr .9fr;gap:40px;align-items:center}
h1{font-size:clamp(38px,6vw,64px);font-weight:800;letter-spacing:-.02em}
.hero p{color:var(--muted);font-size:19px;max-width:46ch;margin:20px 0 28px}
.stage{background:var(--aqua);border-radius:32px;padding:28px;text-align:center}
.stage svg{width:100%;max-width:260px;height:auto}#tooth{transition:fill .35s}
.stage label{display:block;font-weight:700;margin-top:6px}
input[type=range]{width:100%;accent-color:var(--teal);margin:14px 0 4px;padding:0}
.shade{font:700 24px 'Bricolage Grotesque',sans-serif}.stage small{display:block;min-height:3em}
section{padding:72px 0}section h2{font-size:clamp(30px,4vw,44px);margin-bottom:12px}
.lead{color:var(--muted);max-width:56ch;margin:0 0 36px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:26px}
.card h3{font-size:21px;margin:12px 0 8px}.card p{margin:0;color:var(--muted);font-size:16px}
.ico{width:46px;height:46px;border-radius:14px;background:var(--aqua);display:grid;place-items:center;font-size:24px}
.alt{background:var(--aqua)}.alt .card{background:var(--bg)}
.team .card{text-align:center}.avatar{width:84px;height:84px;border-radius:50%;margin:0 auto 12px;background:var(--aqua);display:grid;place-items:center;font:800 28px 'Bricolage Grotesque';color:var(--teal)}
.quote p{font-size:18px;color:var(--ink)}.quote b{display:block;margin-top:12px;color:var(--teal);font-size:15px}
.pills{display:flex;flex-wrap:wrap;gap:12px}.pills span{background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:12px 24px;font-weight:700}
#convenios{padding:44px 0}#convenios h2{font-size:26px}
details{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px 22px;margin-bottom:12px}
summary{font-weight:700;cursor:pointer}details p{margin:10px 0 0;color:var(--muted)}
.booking{display:grid;grid-template-columns:.9fr 1.1fr;gap:40px;align-items:start}
.fcard{background:var(--surface);border:1px solid var(--line);border-radius:24px;padding:28px}
.fcard .p{display:grid;gap:14px}.fcard .p[hidden]{display:none}
label{font-weight:500;font-size:15px;display:grid;gap:6px}
input,select{font:inherit;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);width:100%}
.steps{display:flex;gap:8px;margin-bottom:20px;font-size:14px;font-weight:700}
.steps span{flex:1;padding:8px;border-radius:10px;background:var(--aqua);color:var(--muted);text-align:center}.steps .on{background:var(--teal);color:var(--on)}
.err{color:#D2392B;font-size:14px;font-weight:500;min-height:1.2em}
@media (prefers-color-scheme:dark){.err{color:#FF8E80}}
.nav{display:flex;gap:10px;justify-content:space-between;flex-wrap:wrap}
.slots{display:grid;grid-template-columns:repeat(auto-fill,minmax(76px,1fr));gap:8px}
.slot{padding:10px 0;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;font:inherit;font-weight:500}
.slot[aria-pressed=true]{background:var(--teal);color:var(--on);border-color:var(--teal)}
.slot:disabled{opacity:.4;text-decoration:line-through;cursor:not-allowed}
ul.info{list-style:none;padding:0;margin:0;display:grid;gap:12px}
.rc{background:var(--aqua);border-radius:18px;padding:18px 20px;margin:0 0 14px}
.proto{font:800 22px 'Bricolage Grotesque',sans-serif;color:var(--teal)}
dl{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;margin:12px 0 0}dt{color:var(--muted)}dd{margin:0;font-weight:500}
.b{display:inline-block;padding:2px 10px;border-radius:99px;background:var(--aqua);border:1px solid var(--line);font:700 13px 'DM Sans'}
.b.confirmado{background:#CDEFD8;color:#12532B}.b.pendente{background:#FFE9B8;color:#6B4A00}.b.cancelado{background:#FBD5D0;color:#7A1D12}.b.concluido{background:#D5DEF7;color:#1F3170}
.acts{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}.acts .btn{padding:10px 18px;font-size:15px}
footer{border-top:1px solid var(--line);padding:28px 0;color:var(--muted);font-size:15px}footer .lnk{margin:0 0 0 8px;font-size:15px;text-decoration:underline}
.wa{position:fixed;right:18px;bottom:calc(18px + env(safe-area-inset-bottom,0px));background:#25A55A;color:#fff;border-radius:999px;padding:12px 20px;font-weight:700;text-decoration:none;box-shadow:0 6px 18px rgba(0,0,0,.25);z-index:4}
dialog{background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:24px;padding:26px;width:min(860px,94vw);max-height:90vh}
dialog::backdrop{background:rgba(5,20,28,.6)}
.dh{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.dh h2{font-size:28px;margin:0}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}.row>*{flex:1;min-width:150px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.stat{background:var(--aqua);border-radius:14px;padding:12px 16px;font-weight:500}.stat b{display:block;font:800 30px 'Bricolage Grotesque';color:var(--teal)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.ac button{margin:0 6px 6px 0;padding:5px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;font:inherit;font-size:13px}
@media(max-width:820px){.hero .wrap,.booking,.grid{grid-template-columns:1fr}.hero{padding-top:36px}
.burger{display:grid}nav{display:none;position:absolute;left:0;right:0;top:64px;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 22px 20px;flex-direction:column;align-items:flex-start;gap:14px}
nav.open{display:flex}nav a,nav .lnk{margin:0}header .wrap>.ib:first-of-type{margin-left:auto}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<header><div class="wrap"><a class="logo" href="#topo">DenteHub</a>
<nav id="nv" aria-label="Principal"><a href="#servicos">Serviços</a><a href="#equipe">Equipe</a><a href="#convenios">Convênios</a><a href="#faq">FAQ</a><button class="lnk" id="mb" type="button">Meus Agendamentos</button><a class="btn" href="#agendar" style="color:var(--ctaink);padding:10px 20px;margin-left:22px">Agendar</a></nav>
<button class="ib" id="tg" type="button" aria-label="Alternar entre tema claro e escuro" title="Tema">◐</button>
<button class="ib burger" id="bg" type="button" aria-label="Abrir menu" aria-expanded="false" aria-controls="nv">☰</button></div></header>

<main id="topo">
<div class="hero"><div class="wrap">
<div><h1>Seu sorriso merece cuidado de verdade.</h1>
<p>Odontologia moderna, sem dor e sem pressa. Da limpeza ao implante, a gente explica cada passo antes de começar.</p>
<a class="btn" href="#agendar">Agendar avaliação gratuita</a></div>
<div class="stage" aria-label="Simulador de clareamento">
<svg viewBox="0 0 200 220" role="img" aria-label="Dente"><path id="tooth" fill="#E3C98F" stroke="#0E7C86" stroke-width="5" stroke-linejoin="round" d="M100 28c-18-14-60-14-70 22-8 30 8 52 14 82 5 30 8 60 24 60 14 0 12-40 32-40s18 40 32 40c16 0 19-30 24-60 6-30 22-52 14-82-10-36-52-36-70-22z"/><path d="M62 52c8-8 18-8 26-4" stroke="#fff" stroke-width="7" stroke-linecap="round" fill="none" opacity=".7"/></svg>
<label for="sh">Simule o clareamento</label>
<input id="sh" type="range" min="0" max="4" value="0">
<div class="shade" id="shn">A3,5</div><small id="shd"></small></div>
</div></div>

<section id="servicos" class="alt"><div class="wrap"><h2>O que fazemos</h2><p class="lead">Tratamentos completos para toda a família, com tecnologia que reduz o tempo na cadeira.</p>
<div class="grid">
<div class="card"><div class="ico">✨</div><h3>Clareamento</h3><p>Em consultório ou caseiro, com acompanhamento para evitar sensibilidade.</p></div>
<div class="card"><div class="ico">🦷</div><h3>Implantes</h3><p>Planejamento digital e cirurgia guiada para recuperação mais rápida.</p></div>
<div class="card"><div class="ico">😁</div><h3>Ortodontia</h3><p>Aparelhos fixos e alinhadores transparentes para adultos e adolescentes.</p></div>
<div class="card"><div class="ico">🧼</div><h3>Limpeza e prevenção</h3><p>Profilaxia, flúor e orientação de higiene em retornos a cada seis meses.</p></div>
<div class="card"><div class="ico">🧒</div><h3>Odontopediatria</h3><p>Sala lúdica e atendimento calmo para os pequenos perderem o medo.</p></div>
<div class="card"><div class="ico">🚑</div><h3>Urgência</h3><p>Dor forte, dente quebrado ou inchaço? Atendemos no mesmo dia.</p></div>
</div></div></section>

<section id="equipe" class="team"><div class="wrap"><h2>Quem cuida de você</h2><p class="lead">Profissionais com especialização e muita paciência.</p>
<div class="grid">
<div class="card"><div class="avatar">HA</div><h3>Dra. Helena Aguiar</h3><p>Implantodontia · CRO-PE 12480</p></div>
<div class="card"><div class="avatar">RM</div><h3>Dr. Rafael Moura</h3><p>Ortodontia · CRO-PE 11932</p></div>
<div class="card"><div class="avatar">LC</div><h3>Dra. Letícia Campos</h3><p>Odontopediatria · CRO-PE 13207</p></div>
</div></div></section>

<section id="convenios" class="alt"><div class="wrap"><h2>Convênios aceitos</h2><p class="lead" style="margin-bottom:20px">Atendemos pelos principais planos odontológicos. Também parcelamos em até 12x no cartão.</p>
<div class="pills"><span>Amil Dental</span><span>Bradesco Dental</span><span>OdontoPrev</span><span>SulAmérica</span></div></div></section>

<section id="depoimentos" class="quote"><div class="wrap"><h2>Quem já passou por aqui</h2><p class="lead">O que dizem os pacientes que sentaram na nossa cadeira.</p>
<div class="grid">
<div class="card"><p>“Tinha pavor de dentista. Na primeira consulta eles me explicaram tudo e não senti nada.”</p><b>Mariana S.</b></div>
<div class="card"><p>“Fiz o implante em uma manhã e voltei ao trabalho no dia seguinte. Recomendo demais.”</p><b>Carlos E.</b></div>
<div class="card"><p>“Meu filho pedia pra voltar na clínica. Nunca imaginei ouvir isso.”</p><b>Patrícia L.</b></div>
</div></div></section>

<section id="agendar" class="alt"><div class="wrap booking">
<div><h2>Agende sua avaliação</h2><p class="lead">Escolha o tratamento, o horário e pronto: seu protocolo sai na hora.</p>
<ul class="info"><li>📍 Av. Conselheiro Aguiar, 2333, sala 1204 · Boa Viagem, Recife – PE</li><li>🕘 Seg a sex, 8h às 19h · Sáb, 8h às 12h</li><li>📞 (81) 3042-1180</li><li>💳 Parcelamos em até 12x e aceitamos convênios</li></ul></div>
<div class="fcard">
<form id="f" novalidate>
<div class="steps" id="stp"><span class="on">1 · Tratamento</span><span>2 · Horário</span><span>3 · Seus dados</span></div>
<div class="p" data-p="1">
<label>Especialidade<select id="esp"><option value="">Selecione…</option><option>Avaliação geral</option><option>Clareamento</option><option>Implantes</option><option>Ortodontia</option><option>Limpeza e prevenção</option><option>Odontopediatria</option><option>Urgência</option></select></label>
<label>Profissional<select id="den"><option value="">Sem preferência</option><option value="h">Dra. Helena Aguiar</option><option value="r">Dr. Rafael Moura</option><option value="l">Dra. Letícia Campos</option></select></label>
<small id="hint"></small><div class="err" id="e1" role="alert"></div>
<div class="nav"><span></span><button type="button" class="btn" data-go="2">Continuar</button></div></div>
<div class="p" data-p="2" hidden>
<label>Data<input type="date" id="dt"></label>
<div id="sl" class="slots" role="group" aria-label="Horários disponíveis"></div>
<div class="err" id="e2" role="alert"></div>
<div class="nav"><button type="button" class="btn ghost" data-go="1">Voltar</button><button type="button" class="btn" data-go="3">Continuar</button></div></div>
<div class="p" data-p="3" hidden>
<label>Nome completo<input id="nm" autocomplete="name"></label><div class="err" id="en" role="alert"></div>
<label>Telefone / WhatsApp<input id="tl" type="tel" inputmode="numeric" placeholder="(81) 99999-9999" autocomplete="tel"></label><div class="err" id="et" role="alert"></div>
<label>Modalidade<select id="cv"><option>Particular</option><option>Amil Dental</option><option>Bradesco Dental</option><option>OdontoPrev</option><option>SulAmérica</option></select></label>
<div class="nav"><button type="button" class="btn ghost" data-go="2">Voltar</button><button type="submit" class="btn">Confirmar agendamento</button></div></div>
</form>
<div id="done" hidden></div>
</div></div></section>

<section id="faq"><div class="wrap"><h2>Perguntas frequentes</h2><p class="lead">O que a maioria dos pacientes pergunta antes da primeira visita.</p>
<details><summary>A primeira avaliação realmente é gratuita?</summary><p>Sim. Na primeira visita fazemos exame clínico, conversamos sobre o que você precisa e apresentamos o plano de tratamento com valores, sem compromisso.</p></details>
<details><summary>Quais são as formas de pagamento?</summary><p>Aceitamos Pix, dinheiro e cartões, com parcelamento em até 12x. Também atendemos Amil Dental, Bradesco Dental, OdontoPrev e SulAmérica.</p></details>
<details><summary>Vocês atendem urgências?</summary><p>Atendemos. Em caso de dor forte, dente quebrado ou inchaço, escolha “Urgência” no agendamento ou chame no WhatsApp que encaixamos no mesmo dia.</p></details>
<details><summary>Como remarco ou cancelo uma consulta?</summary><p>Em “Meus Agendamentos”, no topo do site, informe seu telefone ou protocolo e cancele quando quiser. O horário volta a ficar livre para outras pessoas.</p></details>
</div></section>
</main>

<footer><div class="wrap">© 2026 DenteHub · Responsável técnica: Dra. Helena Aguiar, CRO-PE 12480 · <button class="lnk" id="adm" type="button">Área da Recepção</button></div></footer>
<a class="wa" id="wa" href="#" target="_blank" rel="noopener">Falar no WhatsApp</a>

<dialog id="dm" aria-labelledby="tm"><div class="dh"><h2 id="tm">Meus Agendamentos</h2><button class="ib" data-x type="button" aria-label="Fechar">✕</button></div>
<div class="row"><input id="q" placeholder="Telefone ou protocolo (ex.: DH-2026-4821)" aria-label="Telefone ou protocolo"><button class="btn" id="qb" type="button">Buscar</button></div><div id="qr" aria-live="polite"></div></dialog>

<dialog id="da" aria-labelledby="ta"><div class="dh"><h2 id="ta">Área da Recepção</h2><button class="ib" data-x type="button" aria-label="Fechar">✕</button></div>
<form id="lg"><label>Senha<input id="pw" type="password" autocomplete="off"></label><div class="err" id="ep" role="alert"></div><button class="btn" type="submit">Entrar</button></form>
<div id="pn" hidden><div class="stats" id="st"></div>
<div class="row"><label>Data<input type="date" id="fd"></label><label>Dentista<select id="fn"><option value="">Todos</option><option value="h">Dra. Helena Aguiar</option><option value="r">Dr. Rafael Moura</option><option value="l">Dra. Letícia Campos</option></select></label></div>
<div class="tw"><table><thead><tr><th>Protocolo</th><th>Paciente</th><th>Atendimento</th><th>Data</th><th>Status</th><th>Ações</th></tr></thead><tbody id="tb"></tbody></table></div></div></dialog>

<script>
const $=s=>document.querySelector(s),pad=n=>String(n).padStart(2,'0'),iso=d=>d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const DN={h:'Dra. Helena Aguiar',r:'Dr. Rafael Moura',l:'Dra. Letícia Campos'};
const SUG={'Avaliação geral':'h','Clareamento':'h','Implantes':'h','Ortodontia':'r','Limpeza e prevenção':'l','Odontopediatria':'l','Urgência':''};
const L={pendente:'Pendente',confirmado:'Confirmado',concluido:'Concluído',cancelado:'Cancelado'};
const WA='5581999999999';
const wl=t=>'https://wa.me/'+WA+'?text='+encodeURIComponent(t);

/* tema e menu */
const root=document.documentElement;try{const t=localStorage.getItem('dh_theme');if(t)root.dataset.theme=t}catch(e){}
$('#tg').onclick=()=>{const c=root.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'),x=c=='dark'?'light':'dark';root.dataset.theme=x;try{localStorage.setItem('dh_theme',x)}catch(e){}};
const NV=$('#nv'),BG=$('#bg');
BG.onclick=()=>{const o=NV.classList.toggle('open');BG.setAttribute('aria-expanded',o);BG.textContent=o?'✕':'☰'};
NV.addEventListener('click',e=>{if(e.target.closest('a,button')&&NV.classList.contains('open'))BG.click()});
$('#wa').href=wl('Olá! Gostaria de informações sobre atendimento na DenteHub.');

/* simulador */
const S=[["A3,5","#E3C98F","Tom amarelado comum, que escurece com café, vinho e o passar dos anos."],["A3","#EAD3A0","Depois da primeira sessão, o tom já começa a clarear."],["A2","#F0DDB4","Resultado natural, ainda com a cor própria do dente."],["A1","#F6EBD0","Dente bem claro, mantendo aparência natural."],["B1","#FBF5E6","Um dos tons mais claros da escala, indicado para quem busca máximo efeito."]];
const r=$('#sh'),t=$('#tooth'),n=$('#shn'),d=$('#shd');
function u(){const s=S[r.value];t.setAttribute('fill',s[1]);n.textContent='Tom '+s[0];d.textContent=s[2]}
r.addEventListener('input',u);u();

/* agendamento integrado ao backend Python */
const Esp=$('#esp'),Den=$('#den'),Dt=$('#dt'),Sl=$('#sl'),Nm=$('#nm'),Tl=$('#tl'),Cv=$('#cv');
let step=1,hora='';Dt.min=iso(new Date());

async function slots(){
  const dd=Dt.value; Sl.innerHTML='';
  if(!dd){ $('#e2').textContent=''; return; }
  const res = await fetch(`/api/slots?data=${dd}&dent=${Den.value}`);
  const data = await res.json();
  $('#e2').textContent = data.erro || '';
  if(data.erro){ hora=''; return; }
  let stillValid = false;
  data.slots.forEach(s => {
    const x = document.createElement('button');
    x.type='button'; x.className='slot'; x.textContent=s.hora; x.disabled=!s.disponivel;
    x.setAttribute('aria-pressed', s.hora==hora && s.disponivel);
    if(s.hora==hora && s.disponivel) stillValid = true;
    if(!s.disponivel) x.title='Indisponível';
    x.onclick=()=>{hora=s.hora;$('#e2').textContent='';slots()};
    Sl.append(x);
  });
  if(!stillValid) hora='';
}

Esp.onchange=()=>{const s=SUG[Esp.value];Den.value=s||'';hora='';$('#e1').textContent='';$('#hint').textContent=!Esp.value?'':s?'Sugerimos '+DN[s]+' para este tratamento. Você pode trocar.':'Urgência: atendemos com o primeiro profissional disponível.';slots()};
Den.onchange=()=>{hora='';slots()};Dt.onchange=()=>{hora='';slots()};
Tl.oninput=()=>{let v=Tl.value.replace(/\D/g,'').slice(0,11);Tl.value=v.length>7?`(${v.slice(0,2)}) ${v.slice(2,7)}-${v.slice(7)}`:v.length>2?`(${v.slice(0,2)}) ${v.slice(2)}`:v.length?`(${v}`:'';vt()};
Nm.oninput=()=>vn();
const vn=()=>{const ok=Nm.value.trim().split(/\s+/).filter(x=>x.length>1).length>=2;$('#en').textContent=ok||!Nm.value?'':'Informe nome e sobrenome.';return ok};
const vt=()=>{const ok=Tl.value.replace(/\D/g,'').length==11;$('#et').textContent=ok||!Tl.value?'':'Digite os 11 dígitos: (00) 00000-0000.';return ok};

function go(k){
  if(k>step){
    if(step==1&&!Esp.value){$('#e1').textContent='Escolha uma especialidade.';return}
    if(step==2){
      if(!Dt.value){$('#e2').textContent='Escolha uma data.';return}
      if(!hora){$('#e2').textContent='Selecione um horário.';return}
    }
  }
  step=k;
  document.querySelectorAll('.p').forEach(p=>p.hidden=p.dataset.p!=k);
  document.querySelectorAll('#stp span').forEach((s,i)=>s.classList.toggle('on',i==k-1));
  if(k==2)slots();
}
$('#f').addEventListener('click',e=>{const b=e.target.closest('[data-go]');if(b)go(+b.dataset.go)});

const fd=dd=>new Date(dd+'T00:00').toLocaleDateString('pt-BR',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
const card=a=>`<div class="rc"><div class="proto">${esc(a.id)} <span class="b ${a.status}">${L[a.status]}</span></div><dl><dt>Paciente</dt><dd>${esc(a.nome)}</dd><dt>Especialidade</dt><dd>${esc(a.esp)}</dd><dt>Dentista</dt><dd>${DN[a.dent]}</dd><dt>Data</dt><dd>${fd(a.data)}</dd><dt>Horário</dt><dd>${a.hora}</dd><dt>Pagamento</dt><dd>${esc(a.conv)}</dd></dl></div>`;
const msg=a=>`Olá! Segue o comprovante do meu agendamento na DenteHub:\n\nProtocolo: ${a.id}\nPaciente: ${a.nome}\nEspecialidade: ${a.esp}\nDentista: ${DN[a.dent]}\nData: ${fd(a.data)}\nHorário: ${a.hora}\nPagamento: ${a.conv}`;

function showDone(a){
  $('#f').hidden=true;const D=$('#done');D.hidden=false;
  D.innerHTML=`<h3 style="font-size:26px;margin-bottom:12px">Agendamento recebido! 🎉</h3>${card(a)}<p><small>Guarde seu protocolo. Você pode consultar ou cancelar em “Meus Agendamentos”.</small></p><div class="acts"><a class="btn" target="_blank" rel="noopener" href="${wl(msg(a))}">Enviar comprovante no WhatsApp</a><a class="btn ghost" href="/api/ics/${encodeURIComponent(a.id.replace('#',''))}">Adicionar ao Calendário</a><button class="btn ghost" data-new type="button">Novo agendamento</button></div>`;
}

$('#f').onsubmit=async e=>{
  e.preventDefault();
  const a1=vn(),a2=vt();
  if(!Nm.value.trim())$('#en').textContent='Informe seu nome.';
  if(!Tl.value)$('#et').textContent='Informe seu telefone.';
  if(!a1||!a2)return;

  const res = await fetch('/api/agendar', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({nome: Nm.value, tel: Tl.value, esp: Esp.value, dent: Den.value, data: Dt.value, hora, conv: Cv.value})
  });
  const data = await res.json();
  if(!data.ok){
    hora=''; go(2); $('#e2').textContent=data.erro; return;
  }
  showDone(data.agendamento);
  adm();
};

/* meus agendamentos */
const DM=$('#dm'),DA=$('#da');let lastQ='';
$('#mb').onclick=()=>{DM.showModal();$('#q').focus()};
async function mine(){
  const q=lastQ,o=$('#qr');if(!q){o.innerHTML='';return}
  const res = await fetch(`/api/buscar?q=${encodeURIComponent(q)}`);
  const r = await res.json();
  o.innerHTML=r.length?r.map(a=>card(a)+`<div class="acts" style="margin-bottom:18px">${['pendente','confirmado'].includes(a.status)?`<button class="btn ghost" data-cancel="${esc(a.id)}" type="button">Cancelar agendamento</button><a class="btn ghost" href="/api/ics/${encodeURIComponent(a.id.replace('#',''))}">Adicionar ao Calendário</a>`:''}</div>`).join(''):'<p>Nenhum agendamento encontrado para essa busca. Confira o telefone ou o protocolo.</p>';
}
$('#qb').onclick=()=>{lastQ=$('#q').value.trim();mine()};$('#q').onkeydown=e=>{if(e.key=='Enter')$('#qb').click()};

/* recepção */
$('#adm').onclick=()=>{DA.showModal();$('#pw').focus()};
$('#lg').onsubmit=async e=>{
  e.preventDefault();
  const res = await fetch('/api/admin/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({senha: $('#pw').value})
  });
  const data = await res.json();
  if(data.ok){$('#lg').hidden=true;$('#pn').hidden=false;$('#pw').value='';$('#ep').textContent='';adm()}
  else $('#ep').textContent=data.erro;
};
$('#fd').onchange=$('#fn').onchange=()=>adm();
const bt=(a,id,l)=>`<button data-act="${a}" data-id="${esc(id)}" type="button">${l}</button>`;
async function adm(){
  if($('#pn').hidden)return;
  const res = await fetch(`/api/admin/lista?data=${$('#fd').value}&dent=${$('#fn').value}`);
  const {stats, lista} = await res.json();
  $('#st').innerHTML=[['Hoje',stats.hoje],['Pendentes',stats.pendentes],['Confirmados',stats.confirmados]].map(([k,v])=>`<div class="stat"><b>${v}</b>${k}</div>`).join('');
  $('#tb').innerHTML=lista.length?lista.map(a=>`<tr><td>${esc(a.id)}</td><td>${esc(a.nome)}<br><small>${esc(a.tel)} · ${esc(a.conv)}</small></td><td>${esc(a.esp)}<br><small>${DN[a.dent]}</small></td><td>${a.data.split('-').reverse().join('/')}<br>${a.hora}</td><td><span class="b ${a.status}">${L[a.status]}</span></td><td class="ac">${a.status=='pendente'?bt('confirmado',a.id,'Confirmar'):''}${a.status=='confirmado'?bt('concluido',a.id,'Concluir'):''}${['pendente','confirmado'].includes(a.status)?bt('cancelado',a.id,'Cancelar'):''}${bt('del',a.id,'Excluir')}</td></tr>`).join(''):'<tr><td colspan="6">Nenhum agendamento encontrado.</td></tr>';
}

/* eventos globais */
document.addEventListener('click',async e=>{
  const T=e.target;
  if(T.closest('[data-x]'))T.closest('dialog').close();
  if(T.closest('[data-new]')){$('#f').reset();hora='';$('#hint').textContent='';Sl.innerHTML='';$('#done').hidden=true;$('#f').hidden=false;go(1)}
  
  const ca=T.closest('[data-cancel]');
  if(ca&&confirm('Cancelar este agendamento? O horário será liberado.')){
    await fetch('/api/agendamento/acao', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:ca.dataset.cancel, acao:'cancelado'})});
    slots(); adm(); mine();
  }
  const ac=T.closest('[data-act]');
  if(ac){
    const id=ac.dataset.id, act=ac.dataset.act;
    if(act=='del' && !confirm('Excluir este agendamento definitivamente?')) return;
    if(act=='cancelado' && !confirm('Cancelar este agendamento?')) return;
    await fetch('/api/agendamento/acao', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, acao:act})});
    slots(); adm(); mine();
  }
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, port=5000)