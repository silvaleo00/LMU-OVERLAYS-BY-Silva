# LMU Overlays

Overlays para o **Le Mans Ultimate** e o **iRacing** em estilo de transmissão de TV (faixas inclinadas na cor da
classe, fonte condensada). São janelas transparentes por cima do jogo, a ler a telemetria diretamente da
memória partilhada do jogo (`LMU_Data` no LMU, o iRacing SDK no iRacing). Há 6 línguas: English, Português, Español, Français,
Deutsch e Italiano.

## Simuladores

No painel, **Simulador** escolhe o jogo: **Le Mans Ultimate** ou **iRacing** (a app troca na hora).

| | Le Mans Ultimate | iRacing |
|---|---|---|
| Preparar | Definições › Gameplay › **Enable Plugins: ON** | nada (a telemetria está sempre ligada) |
| Ecrã | Borderless ou janela | Borderless ou janela |
| Radar (Blind Spot) | posições reais dos carros | à frente/atrás pela distância; de lado pelo spotter do iRacing |
| Mapa | posições reais | traçado desenhado na 1.ª volta a partir da tua velocidade; carros pela distância |
| Energia virtual | sim | não (só litros) |
| "BOX, BOX." | quando pedes boxes | quando um carro (ou tu) entra na via das boxes |
| Pneus | ao vivo | o iRacing só atualiza temperaturas e desgaste nas boxes |
| Track limits | pontos de track limits do jogo | pontos de incidente |
| Danos | carroçaria por zona, aero, rodas | tempo de reparação nas boxes |
| Previsão de chuva | previsão do jogo (API local) + tendência | tendência |

Os mapas e as voltas de referência do delta ficam guardados à parte para cada simulador.

## Overlays

| Overlay | O que mostra |
|---|---|
| **Blind Spot** | Radar visto de cima com os carros à tua volta e barras laterais (amarelo = ao lado, vermelho = colado; "3 lado a lado"). Só aparece quando há alguém perto. |
| **Delta Bar** | Delta para a melhor volta, barra verde/vermelha com seta de tendência, tempo previsto. A melhor volta fica guardada por pista+carro. |
| **Fuel Calculator** | Litros ou **energia virtual** (deteta sozinho). Média por volta, voltas que dá, voltas até ao fim, quanto adicionar, paragens, consumo alvo. |
| **Relative** | Os 3 carros à frente e os 3 atrás em pista, com gap. Vermelho = está voltas à frente, azul = estás a dar-lhe volta. |
| **Timing Tower** | Classificação estilo WEC. Alterna sozinha entre 5 ecrãs: **intervalo**, **gap ao líder** (só a tua classe), **nome do piloto**, **nome da equipa** e **top 8 de cada classe**. Em treino/quali mostra as melhores voltas da tua classe. Placa na cor da marca, código de 3 letras do piloto, tempos em caixas, "BOX" quando está nas boxes. Volta acabada a dourado (roxo = melhor da classe, verde = melhor pessoal); carro parado com a linha amarela a piscar. No estilo WEC 2025 o emblema do topo muda de cor com a bandeira (verde, amarela, vermelha). |
| **Battle** | Tu e os carros à frente e atrás na tua classe, com o intervalo numa faixa vermelha (≤0.3 s) ou âmbar (≤0.5 s) e quanto o gap muda por volta. Por defeito só em corrida. |
| **Flags** | Bandeira com texto: vermelha, xadrez, FCY (com estado das boxes), amarela à frente (com distância ao carro lento), azul (e quem te quer passar), penalidade, partida. |
| **Digital Flag** | A mesma bandeira num painel de LEDs, como os painéis digitais à beira da pista. |
| **Team Radio** | O cartão "BOX, BOX." das transmissões, na cor da equipa, com o número, o nome da equipa e uma onda de rádio animada. Aparece quando pedes boxes e quando um rival da tua classe perto de ti pede boxes ou entra no pit lane. |
| **Pitbox Helper** | Aparece quando pedes boxes ou estás no pit lane: distância à tua box com aviso de travagem, velocidade, limitador, combustível a pôr, tempo parado. |
| **Track Map** | O traçado com todos os carros na cor da classe. O desenho grava-se na tua primeira volta completa em cada pista e fica guardado. |
| **Input Graphics** | Barra compacta com módulos que ligas/desligas: mudança + velocidade + luzes de TC/ABS, volante, gráfico dos comandos (acelerador, travão, embraiagem, direção, marcas onde o ABS/TC atuou) e pedais com %. Volante opcional: simples (com RPM, mudança e velocidade), normal, GT, fórmula, F1, antigo, rali, camião, barco ou **uma foto do teu volante** (PNG). |
| **Advanced Panel** | Velocidade, mudança, RPM com luzes de mudança, TC/CUT/SLIP, ABS, repartição de travagem, mapa do motor, bateria. |
| **Track Limits** | Aviso vermelho a piscar quando apanhas um track limit, com os pontos que tens e quantos faltam para a penalização; verde quando fazes uma volta limpa. No iRacing usa os pontos de incidente (e o limite da sessão). |
| **Damage** | O carro visto de cima com a carroçaria em 8 zonas (amarelo = algum, vermelho = muito), rodas furadas/soltas, aerodinâmica, motor (sobreaquecimento, pressões) e há quanto tempo foi o último toque. No iRacing (sem danos por zona) mostra os segundos de reparação obrigatória e opcional. |
| **Weather Forecast** | % de água na pista (média e intervalo mín–máx), seco/húmido/molhado/encharcado, intensidade da chuva, céu e **daqui a quantas voltas vai chover ou secar**. Usa a previsão do jogo quando existe (LMU) e, senão, a tendência dos últimos minutos; diz qual das duas está a usar. |
| **Lap Counter** | Volta atual, total de voltas ou, em corridas por tempo, as voltas que faltam (estimativa) e o tempo. |
| **Engine Temps** | Água e óleo (e motor elétrico do híbrido) com barra e aviso a amarelo/vermelho. Os limites mudam-se no `config.json`. |
| *Standings* (extra) | A classificação anterior, em tabela. Desligada por defeito (a Timing Tower substitui-a). |
| *Tyres* (extra) | Temperaturas esq/centro/dir, pressão, desgaste, carcaça, travões. Desligado por defeito. |
| *Wind & Weather* (extra) | Vento relativo ao carro, temperaturas, chuva. Desligado por defeito. |

## Estilos

No painel, **Estilo** muda o visual de todos os overlays de uma vez:

| Estilo | Visual |
|---|---|
| **WEC 2025** (por defeito) | o gráfico da WEC de 2025: torre azul-escura com emblema e relógio, faixas vermelhas em itálico, placas na cor da marca, tempos em caixas cinzentas, nome do circuito em baixo |
| **WEC Broadcast** | o anterior: cabeçalho branco, separador preto, blocos sólidos, néon azul |
| **Cyber Neon** | roxo-escuro com contornos néon azul e rosa, a tua linha a brilhar a rosa |
| **Glass** | vidro escuro translúcido, cantos redondos, sem néon, discreto |
| **Carbon** | preto com textura de carbono e vermelho, linhas inclinadas, estilo F1 |
| **HUD** | quase sem fundos, só texto com sombra; o que menos tapa a pista |
| **Retro Endurance** | painéis creme, azul-escuro e laranja, estilo corridas clássicas |
| **Horizon Pop** | gradientes rosa→laranja, painéis bem inclinados, chevrons, a tua linha em gradiente |
| **Aurora** | vidro roxo→azul com cápsulas redondas e a tua linha em gradiente azul→violeta |
| **Hologram** | sci-fi: cantos de mira, cantos cortados, linhas de varrimento, tudo em ciano |
| **Capsule** | cápsulas pretas muito redondas, azul vivo e rosa (tipo "ilha" de telemóvel) |
| **Inferno** | preto e brasas: gradientes vermelho→laranja, chevrons e brilho quente |

A cor de destaque em **Auto** usa a cor de cada estilo; escolher outra sobrepõe-se.

## Néon

Contornos e tubos de luz na cor de destaque (escolhida no painel), LEDs de mudança e barras com
brilho, a tua linha marcada a âmbar, bandeiras e lutas renhidas a brilhar na sua cor. Desliga-se
na caixa **Brilho néon** do painel (ou `global.neon` no `config.json`).

## Modo Auto: menos coisas no ecrã

Cada overlay tem modo **Auto** ou **Sempre** (coluna "Modo" no painel). Em Auto aparecem com
um fade quando interessam e desaparecem a seguir:

| Overlay | Em Auto aparece… |
|---|---|
| Timing Tower | sempre, mas como **mini-torre** (tu + carro à frente e atrás); expande ao fechares uma volta, quando mudas de posição, em FCY, nas boxes e no início |
| Relative | quando há um carro a ≤1.2 s (`near_s`), com bandeira azul ou ao sair das boxes |
| Battle | quando há luta: alguém da tua classe a ≤1.5 s (`battle_s`) |
| Delta Bar | treino/quali: sempre; corrida: uns segundos depois de cada setor e volta |
| Fuel | depois de cada volta, nas boxes, em FCY e quando o depósito não chega |
| Track Map | no início, depois de cada volta, com amarelas/FCY e nas boxes |
| Tyres / Wind | depois de cada volta e com pneus fora da janela / ao sair das boxes e com chuva |
| Flags, Digital Flag, Pitbox, Blind Spot | só quando há alguma coisa (bandeira, boxes, carro ao lado) |
| Track Limits | quando apanhas um (vermelho) e no fim de uma volta limpa (verde) |
| Damage | quando há danos ou logo a seguir a um toque |
| Weather Forecast | com chuva ou água na pista, quando vai mudar nas próximas 10 voltas, no início e depois de cada volta |
| Engine Temps | perto do limite de aviso, no início, ao sair das boxes e depois de cada volta |
| Team Radio | uns segundos quando tu ou um rival perto pedem boxes |

**Espreitar** (`Ctrl+Shift+Espaço` ou um botão do volante) mostra tudo completo durante 8 s.

## Botões do volante

No painel, em "Botões do volante e teclas", carrega em **Atribuir** e depois no botão do volante
(ou button box) que queres usar. Ações: espreitar, mudar o campo da Torre, esconder tudo,
desbloquear. Lê os primeiros 32 botões de cada dispositivo; se um botão não for detetado, mapeia-o
para uma tecla no software do volante (Moza Pit House) e usa o atalho de teclado.

## Desempenho (pouco impacto nos FPS do jogo)

No painel, **Sistema › Desempenho**: **Leve** (10 fps), **Equilibrado** (20, recomendado) ou **Suave** (40). Nos modos Leve e Equilibrado as partes que mexem não têm brilho néon (menos pintura).

- Cada overlay só se redesenha quando o que mostra muda; os de texto (torre, relativo, combustível,
  meteorologia…) só 1–10 vezes por segundo, porque o jogo só atualiza as posições ~5x/s.
- Sem jogo ou sem nada à vista, a app lê só 5x por segundo (quase zero CPU).
- **Abranda sozinha**: se a app começar a gastar mais de 20% do tempo de cada frame, baixa os fps; volta a subir quando há folga.
- Corre com prioridade abaixo do normal e, nos modos Leve/Equilibrado, em "modo eficiência" do Windows
  (núcleos de eficiência nos processadores que os têm), longe do jogo.
- Já não muda a resolução do temporizador do Windows.
- O fundo de cada overlay é desenhado uma vez e reaproveitado; as janelas encolhem quando o conteúdo fica mais pequeno.
- O painel mostra os fps reais e os ms por frame.

## Preparar o jogo

1. **Definições → Gameplay → Enable Plugins: ON**. Sem isto o jogo não publica os dados.
2. Ecrã em **Borderless** (ou Windowed). Em Fullscreen exclusivo os overlays não aparecem.

## Usar

- Com Python: `instalar.bat` uma vez, depois `iniciar.bat` (ou `demo.bat` para dados simulados).
- Versão `.exe`: abre `LMU Overlays.exe`. Não precisa de Python.

O painel tem um menu à esquerda: **Início** (simulador, estado, mover/mostrar/esconder, atualizações), **Overlays** (agrupados por tema, com uma frase a explicar cada um), **Aspeto** (estilo com pré-visualização, cores, língua, unidades), **Comandos e volante**, **Botões e atalhos** e **Sistema**.

No painel:
- **Língua**, cor de destaque, km/h ou mph, kPa/psi/bar.
- Cada overlay tem uma caixa para o ligar e três para escolher em que sessões aparece:
  **T**reino, **Q**ualificação, **C**orrida (ex.: Delta só em treino e quali).
- **Desbloquear para mover**: arrasta e usa a roda do rato para o tamanho; depois bloqueia.

Atalhos (funcionam com o jogo em primeiro plano):

| Atalho | Faz |
|---|---|
| `Ctrl+Shift+Espaço` | espreitar: mostra tudo durante 8 s |
| `Ctrl+Shift+T` | Torre: ecrã seguinte (intervalo → gap → última → melhor → paragens → piloto → equipa → top 8 → automático) |
| `Ctrl+Shift+O` | esconder / mostrar todos os overlays |
| `Ctrl+Shift+L` | desbloquear / bloquear para mover |
| `Ctrl+Shift+P` | abrir o painel para ligar/desligar overlays |

Mudam-se em `config.json` → `global.hotkeys`.

## Atualizações automáticas

Publicas uma versão nova com **duplo clique em `publicar_versao.bat`** (escreves o número e o que
mudou). O GitHub compila o `.exe` e cria a Release. A app dos teus amigos vê que há versão nova e
mostra no painel o botão **"Atualizar para X"**: um clique descarrega, fecha, troca os ficheiros
(sem mexer no `config.json` nem na pasta `data`) e volta a abrir. A preparação (uma vez só) está
no `GUIA_ATUALIZACOES.txt`.

## Partilhar com amigos (sem Python)

1. No teu PC, duplo clique em **`criar_exe.bat`**. Corre os testes e gera
   **`dist\LMU_Overlays_Windows.zip`** (uns 2 minutos).
2. Envia o zip. Eles extraem e abrem `LMU Overlays.exe`. O `LEIA-ME.txt` lá dentro (PT + EN)
   explica o resto.

O `.exe` não é assinado, por isso o Windows mostra "O Windows protegeu o computador" na primeira
vez: **Mais informações → Executar mesmo assim**. Alternativa sem Python nenhum: põe o projeto
num repositório GitHub e corre **Actions → build-windows-exe → Run workflow**.

## Afinar (`config.json`, só para quem desenvolve)

Os utilizadores mexem em tudo pelo painel. No `.exe`, as definições ficam escondidas em `%APPDATA%\LMU Overlays`; com Python, na pasta do projeto.

Opções por overlay:

| Overlay | Opções |
|---|---|
| `blind_spot` | `range_long_m`, `range_lat_m`, `always_show`, `flip_sides` |
| `delta` | `bar_range` (segundos para a barra ficar cheia), `race_show_s` |
| `fuel` | `margin_laps`, `avg_laps` |
| `relative` | `rows_ahead`, `rows_behind`, `show_last_lap`, `show_pit_cars`, `near_s` |
| `tower` | `fields` (ecrãs em corrida, lista de: `interval`, `gap`, `name`, `team`, `top`, `last`, `best`, `pits`), `quali_fields` (em treino/quali), `cycle_s`, `top_n`, `player_class_rows`, `other_class_rows`, `show_other_classes`, `lap_flash_s`, `slow_kmh`, `title` (texto do emblema, ex.: o nome da tua liga), `footer` (texto em baixo; vazio = circuito) |
| `team_radio` | `show_s`, `show_player`, `rivals` (`near`, `class`, `all`, `off`), `rival_range` |
| `battle` | `ahead`, `behind` (nº de carros de cada lado), `red_s`, `amber_s`, `battle_s` |
| `standings` | `player_class_rows`, `other_class_rows`, `show_other_classes`, `player_class_first` |
| `flags`, `digital_flag` | `yellow_range_m`, `slow_kmh`, `blue_lookback_m` (+ `show_when_clear` no digital) |
| `pitbox` | `approach_m`, `decel` (m/s² usados para o aviso de travagem) |
| `track_map` | `size`, `mirror`, `show_pit_cars` |
| `inputs` | `window_s`, `trace_w`, `show_gear`, `show_wheel`, `show_trace`, `show_pedals`, `show_clutch`, `show_steering_trace`, `show_aids`, `wheel` (`simple`, `normal`, `gt`, `formula`, `f1`, `old_school`, `rally`, `truck`, `boat`, `custom`), `wheel_image` |
| `track_limits` | `warn_s`, `clean_s` |
| `weather` | `warn_laps` |
| `engine_temps` | `water_warn`, `water_hot`, `oil_warn`, `oil_hot`, `hybrid_warn`, `hybrid_hot`, `fahrenheit` |
| `advanced` | `shift_start`, `shift_full` (fração das RPM máximas para as luzes) |
| `wind` | `flip_lateral`, `flip_longitudinal` |
| todos | `enabled`, `sessions`, `mode` (`auto`/`always`), `x`, `y`, `scale`, `fps` |

Em `global`: `sim` (`lmu` ou `iracing`), `hz` (fps), `skin`, `language`, `accent`, `speed_unit`, `pressure_unit`, `opacity`, `hotkeys`, `buttons`,
`peek_s`, `low_priority`, `hide_when_not_driving`, `class_rules` (siglas e cores das classes).

## Notas

- **Ainda não testado com o jogo aberto nesta versão**: testei a leitura com a estrutura do LMU
  preenchida artificialmente, todos os overlays e estados com dados simulados, e o fluxo da app.
  Se algo mostrar "error", o detalhe fica em `lmu_overlays.log`.
- **Lados do Blind Spot / Vento**: dependem da convenção de eixos do jogo. Se aparecerem
  trocados, liga `flip_sides` (Blind Spot) ou `flip_lateral` (Vento).
- **Vento**: o LMU pode não preencher o campo do vento; nesse caso o overlay diz que não há dados.
- **Consumo**: só conta voltas limpas (sem boxes, sem reabastecer, sem FCY).
- **Track Map**: na primeira volta numa pista nova o desenho vai aparecendo enquanto conduzes.

## Testes

```
py tests\test_core.py
py run.py --preview      (PNG em .\previews; precisa de: py -m pip install pillow)
```

## Créditos

- Estruturas da memória partilhada: [pyLMUSharedMemory](https://github.com/TinyPedal/pyLMUSharedMemory) (MIT).
- Fonte: Barlow Semi Condensed (SIL Open Font License, em `assets/fonts/OFL.txt`).
