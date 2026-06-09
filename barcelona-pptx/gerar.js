const pptxgen = require("pptxgenjs");

const C = {
  accent:      "1A3C34",
  accentLight: "006451",
  paper:       "D7D1CA",
  ink:         "1a1410",
  muted:       "7A6755",
  white:       "FFFFFF",
  highlight:   "E8E3DC",
  tagBg:       "C8C2BB",
  alertGreen:  "006451",
  callout:     "E8F0EE",
};

const makeShadow = () => ({ type: "outer", color: "1A3C34", blur: 6, offset: 2, angle: 135, opacity: 0.12 });

let pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "Residencial Barcelona — Narrativa dos Fatos";

// SLIDE 0 — CAPA
{
  let s = pres.addSlide();
  s.background = { color: C.accent };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.muted }, line: { color: C.muted } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.12, w: 10, h: 0.03, fill: { color: C.muted }, line: { color: C.muted } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.06, fill: { color: C.muted }, line: { color: C.muted } });
  s.addText("AÇÃO ORDINÁRIA — MUNICÍPIO DE BETIM/MG", { x: 0.5, y: 0.9, w: 9, h: 0.4, fontSize: 9, color: C.tagBg, charSpacing: 4, align: "center", fontFace: "Georgia" });
  s.addText("Residencial Barcelona", { x: 0.5, y: 1.45, w: 9, h: 1.1, fontSize: 48, bold: true, color: C.white, align: "center", fontFace: "Georgia" });
  s.addText("Narrativa dos Fatos", { x: 0.5, y: 2.55, w: 9, h: 0.7, fontSize: 28, bold: false, color: C.tagBg, align: "center", italic: true, fontFace: "Georgia" });
  s.addShape(pres.shapes.RECTANGLE, { x: 3.5, y: 3.35, w: 3, h: 0.02, fill: { color: C.muted }, line: { color: C.muted } });
  s.addText("56 documentos  ·  7 pontos  ·  Organizado por ordem cronológica dos fatos", { x: 0.5, y: 3.55, w: 9, h: 0.4, fontSize: 12, color: C.tagBg, align: "center", fontFace: "Calibri" });
  s.addText("Residencial Barcelona Incorporações SPE Ltda. e Construtora Você Eireli  v.  Município de Betim\nAção Ordinária — Vara Empresarial, Fazenda Pública e Autarquias — Comarca de Betim/MG", { x: 0.5, y: 4.7, w: 9, h: 0.7, fontSize: 9, color: C.tagBg, align: "center", italic: true, fontFace: "Calibri" });
}

// SLIDE 1 — Documentos de Qualificação
{
  let s = pres.addSlide();
  s.background = { color: C.paper };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.05, fill: { color: C.highlight }, line: { color: C.tagBg } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 1.05, fill: { color: C.muted }, line: { color: C.muted } });
  s.addText("DOCUMENTOS DE QUALIFICAÇÃO DAS PARTES", { x: 0.3, y: 0.06, w: 9.4, h: 0.42, fontSize: 9, color: C.muted, charSpacing: 3, fontFace: "Georgia", bold: false });
  s.addText("(não integram a narrativa dos fatos)", { x: 0.3, y: 0.48, w: 9.4, h: 0.38, fontSize: 13, color: C.accent, fontFace: "Georgia", italic: true });
  const docs0 = [
    "Doc. 1  · 9719657334 — Contrato Social Residencial Barcelona",
    "Doc. 2  · 9719663712 — CNPJ Residencial Barcelona",
    "Doc. 3  · 9719657339 — Procuração Residencial Barcelona",
    "Doc. 4  · 9719663713 — Contrato Social Construtora Você",
    "Doc. 5  · 9719663714 — CNPJ Construtora Você",
    "Doc. 6  · 9719657340 — Procuração Construtora Você",
    "Doc. 7  · 9719660869 — Substabelecimento",
  ];
  docs0.forEach((d, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.3 + col * 4.85, y = 1.22 + row * 0.75;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.55, h: 0.55, fill: { color: C.white }, line: { color: C.tagBg }, shadow: makeShadow() });
    s.addText(d, { x: x + 0.12, y: y + 0.08, w: 4.3, h: 0.4, fontSize: 10.5, color: C.ink, fontFace: "Calibri" });
  });
}

function addSectionSlide({ pontoLabel, title, period, paragraphs, callout, isAlert }) {
  let s = pres.addSlide();
  s.background = { color: C.white };
  const barColor = isAlert ? C.accentLight : C.muted;
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: barColor }, line: { color: barColor } });
  s.addText(pontoLabel, { x: 0.25, y: 0.22, w: 9.5, h: 0.32, fontSize: 8.5, color: barColor, charSpacing: 3, fontFace: "Georgia" });
  s.addText(title, { x: 0.25, y: 0.52, w: 9.5, h: 0.65, fontSize: 19, bold: true, color: C.ink, fontFace: "Georgia", lineSpacingMultiple: 1.1 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 1.2, w: 2.1, h: 0.3, fill: { color: C.tagBg }, line: { color: C.tagBg } });
  s.addText(period, { x: 0.25, y: 1.2, w: 2.1, h: 0.3, fontSize: 9, color: C.accent, align: "center", fontFace: "Calibri" });
  let yPos = 1.62;
  paragraphs.forEach(p => {
    s.addText(p, { x: 0.25, y: yPos, w: 9.5, h: 0.55, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
    yPos += 0.6;
  });
  if (callout) {
    yPos = Math.max(yPos, 3.6);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: yPos, w: 9.5, h: 0.55, fill: { color: C.callout }, line: { color: C.accentLight } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: yPos, w: 0.06, h: 0.55, fill: { color: C.accent }, line: { color: C.accent } });
    s.addText(callout, { x: 0.42, y: yPos + 0.05, w: 9.2, h: 0.45, fontSize: 9.5, italic: true, color: C.accent, fontFace: "Calibri", valign: "middle" });
  }
  return s;
}

function addDocSlide({ ponto, title, docs, isAlert }) {
  let s = pres.addSlide();
  s.background = { color: C.highlight };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText(`${ponto} — Documentos`, { x: 0.25, y: 0.1, w: 9.5, h: 0.35, fontSize: 11, color: C.white, fontFace: "Georgia", italic: true });
  s.addText(title, { x: 4.5, y: 0.1, w: 5, h: 0.35, fontSize: 9, color: C.tagBg, fontFace: "Calibri", align: "right" });
  const cols = 2, tagH = 0.48, tagW = 4.6, startY = 0.7;
  docs.forEach((d, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = 0.15 + col * (tagW + 0.25), y = startY + row * (tagH + 0.1);
    if (y + tagH > 5.5) return;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: tagW, h: tagH, fill: { color: C.white }, line: { color: C.tagBg }, shadow: makeShadow() });
    const parts = d.match(/^(Doc\.\s*\S+)\s+(.*)/);
    if (parts) {
      s.addText(parts[1], { x: x + 0.1, y: y + 0.07, w: 1.0, h: 0.32, fontSize: 9, color: C.accent, bold: true, fontFace: "Calibri" });
      s.addText(parts[2], { x: x + 1.15, y: y + 0.07, w: tagW - 1.25, h: 0.32, fontSize: 9, color: C.ink, fontFace: "Calibri" });
    } else {
      s.addText(d, { x: x + 0.1, y: y + 0.07, w: tagW - 0.2, h: 0.32, fontSize: 9, color: C.ink, fontFace: "Calibri" });
    }
  });
}

// PONTO 1
addSectionSlide({
  pontoLabel: "PONTO 1 — ORIGEM DO EMPREENDIMENTO E DEFINIÇÃO DA CONTRAPARTIDA",
  title: "Consulta prévia ao Município e constituição da SPE (2016–2017)",
  period: "2016 – 2017", isAlert: false,
  paragraphs: [
    "Antes de empreender, a 2ª Autora consultou o Município de Betim sobre qual contrapartida seria exigida para um empreendimento nos moldes do Residencial Barcelona. Em 06/07/2016, o Réu apresentou 4 opções. Com a viabilidade confirmada, a 1ª Autora foi constituída em 29/09/2016 como SPE com propósito específico de edificar o empreendimento.",
    "Em 17/10/2016, o Réu comunicou que a contrapartida seria exclusivamente a realização de obras viárias, no valor fixo e irreajustável de R$ 1.571.429,92. Com base nessa definição, o terreno foi adquirido em 13/02/2017 e, em 06/04/2017, firmou-se o Termo de Aceite CAEAI, que confirmava a contrapartida única e seu custo total.",
  ],
  callout: "Base fática central: a viabilidade econômica do empreendimento foi calculada sobre a contrapartida definida pelo próprio Réu em 2016.",
});
addDocSlide({ ponto: "Ponto 1", title: "Consulta prévia ao Município e constituição da SPE (2016–2017)", isAlert: false, docs: ["Doc. 8  9719671751 — Matrícula do imóvel", "Doc. 9  9719671752 — Termo CAEAI + atas deliberações"] });

// PONTO 2
addSectionSlide({
  pontoLabel: "PONTO 2 — LICENCIAMENTO REGULAR E INÍCIO DAS OBRAS",
  title: "Aprovação do projeto, alvará e registro da incorporação (2017)",
  period: "2017", isAlert: false,
  paragraphs: [
    "Em 27/04/2017, o projeto foi aprovado pela Prefeitura de Betim. Em 03/05/2017, foi emitido o Alvará de Construção nº 81/2017 com validade até 24/12/2018, já com caráter provisório e condicionado à aprovação do projeto de ligação viária. Em 19/06/2017, realizou-se o Registro de Incorporação Imobiliária, com instituição de condomínio e patrimônio de afetação.",
    "O empreendimento contava com 368 apartamentos, 25 lojas e 490 vagas, financiado em três módulos pela Caixa Econômica Federal. A partir de 04/07/2017, as Autoras passaram a cobrar o Réu sobre a autorização para início das obras de contrapartida.",
  ],
  callout: null,
});
addDocSlide({ ponto: "Ponto 2", title: "Aprovação do projeto, alvará e registro da incorporação (2017)", isAlert: false, docs: ["Doc. 10  9719671753 — Alvará de aprovação do projeto", "Doc. 11  9719672601 — Alvará renovado c/ condicionante", "Doc. 41  9719683303 — Contrato Financiamento Módulo I", "Doc. 42  9719683304 — Contrato Financiamento Módulo II", "Doc. 43  9719683305 — Contrato Financiamento Módulo III", "Doc. 44  9719683306 — Contrato com Adquirente (Lucinete)"] });

// PONTO 3 — slide 1
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.accentLight }, line: { color: C.accentLight } });
  s.addText("PONTO 3 — 1a GRAVE ILEGALIDADE: CRIACAO DA CONTRAPARTIDA SOCIAL", { x: 0.25, y: 0.22, w: 9.5, h: 0.32, fontSize: 8.5, color: C.accentLight, charSpacing: 2, fontFace: "Georgia" });
  s.addText("Lei 6.228/2017 e Decreto 40.886/2017 — exigência inconstitucional superveniente (ago–set/2017)", { x: 0.25, y: 0.52, w: 9.5, h: 0.65, fontSize: 17, bold: true, color: C.ink, fontFace: "Georgia", lineSpacingMultiple: 1.1 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 1.2, w: 1.6, h: 0.3, fill: { color: C.tagBg }, line: { color: C.tagBg } });
  s.addText("ago–set/2017", { x: 0.25, y: 1.2, w: 1.6, h: 0.3, fontSize: 9, color: C.accent, align: "center", fontFace: "Calibri" });
  s.addText("O Decreto Municipal no 40.886, de 12/09/2017, regulamentou a Lei Municipal no 6.228/2017, instituiu a Comissão de Avaliação de Contrapartidas Sociais e Doação ou Cessão de Imóveis Públicos (CACS) e passou a condicionar a expedição dos alvarás de construção e de funcionamento, bem como da certidão de baixa e habite-se, à assinatura dos termos respectivos e ao cumprimento das contrapartidas, criando exigência que não encontra amparo no Código de Obras do Município de Betim, instituído pela Lei Municipal no 5.116/2011.", { x: 0.25, y: 1.62, w: 9.5, h: 0.7, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addText("Na sequência, o Município editou o Decreto Municipal no 41.251, de 30/05/2018, alterando o inciso I do art. 5o do Decreto no 40.886/2017 para restringir a incidência da contrapartida social aos empreendimentos residenciais com 21 ou mais unidades. Poucos dias depois, o Decreto no 41.261, de 06/06/2018, revogou o Decreto no 41.251/2018 e restabeleceu a exigência para empreendimentos com 10 ou mais unidades habitacionais.", { x: 0.25, y: 2.4, w: 9.5, h: 0.7, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addText("O SINDUSCON/MG ajuizou a ADIn no 0895080-28.2017.8.13.0000, impugnando a Lei no 6.228/2017 e o Decreto no 40.886/2017. O Órgão Especial do TJMG, em 22/10/2018, deferiu cautelar para suspender a eficácia da legislação municipal, por extrapolação da competência municipal e indevida transferência ao particular de encargos de obras públicas.", { x: 0.25, y: 3.18, w: 9.5, h: 0.65, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 3.95, w: 9.5, h: 0.55, fill: { color: C.callout }, line: { color: C.accentLight } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 3.95, w: 0.06, h: 0.55, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("O Réu exigiu a Contrapartida Social apesar de ela ser posterior à aprovação do projeto, ao alvará, ao registro de incorporação e à definição original da contrapartida.", { x: 0.42, y: 4.0, w: 9.2, h: 0.45, fontSize: 9.5, italic: true, color: C.accent, fontFace: "Calibri", valign: "middle" });
}

// PONTO 3 — slide 2
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.accentLight }, line: { color: C.accentLight } });
  s.addText("PONTO 3 (continuação) — 1a GRAVE ILEGALIDADE", { x: 0.25, y: 0.22, w: 9.5, h: 0.32, fontSize: 8.5, color: C.accentLight, charSpacing: 2, fontFace: "Georgia" });
  s.addText("Lei 6.448/2018 — Nova norma, mesma lógica inconstitucional", { x: 0.25, y: 0.52, w: 9.5, h: 0.65, fontSize: 17, bold: true, color: C.ink, fontFace: "Georgia" });
  s.addText("Não obstante a suspensão cautelar do primeiro diploma, o Município editou, em 20/12/2018, a Lei Municipal no 6.448/2018, que revogou expressamente a Lei no 6.228/2017, mas preservou a mesma lógica de imposição de medidas compensatórias sociais como condição para a regularização urbanística do empreendimento.", { x: 0.25, y: 1.3, w: 9.5, h: 0.65, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addText("Referida norma foi igualmente impugnada na ADIn no 0168468-26.2019.8.13.0000, ajuizada em 18/02/2019 pelo SINDUSCON/MG, tendo o TJMG concedido nova medida cautelar para suspender a sua eficácia, com julgamento em 08/07/2019 e publicação da súmula em 17/11/2020.", { x: 0.25, y: 2.05, w: 9.5, h: 0.65, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
}

addDocSlide({ ponto: "Ponto 3", title: "1a Grave Ilegalidade — Contrapartida Social", isAlert: true, docs: ["Doc. 12  9719672602 — Acordão cautelar ADIn 1 (Lei 6.228/17)", "Doc. 12A  9719672603 — Inicial ADIn 1", "Doc. 18  9719672609 — Acordão cautelar ADIn 2 (Lei 6.448/18)", "Doc. 18A  9719672610 — Inicial ADIn 2", "Doc. 19  9719672611 — Declaração Sinduscon-MG", "Doc. 49  9719683314 — Código de Obras Betim (Lei 5.116/2011)", "Doc. 50  9719683315 — Lei 6.228/17", "Doc. 50A  9719683316 — PL Lei 6.228/17", "Doc. 51  9719683317 — Decreto 40.886/17", "Doc. 52  9719683318 — Decreto 41.251/18", "Doc. 53  9719683319 — Decreto 41.261/18", "Doc. 54  9719683320 — Lei 6.391/18", "Doc. 55  9719683321 — Lei 6.448/18", "Doc. 55A  9719683322 — PL Lei 6.448/18", "Doc. 56  9719683323 — Decreto 41.515/19"] });

// PONTO 4
addSectionSlide({
  pontoLabel: "PONTO 4 — 2a GRAVE ILEGALIDADE: NEGATIVA DO ALVARÁ, EMBARGO E PARALISAÇÃO",
  title: "Obra paralisada por ato ilegal do Réu (dez/2018 – jan/2019)",
  period: "dez/2018 – jan/2019", isAlert: true,
  paragraphs: [
    "Com o alvará provisório vencendo em 24/12/2018, as Autoras solicitaram a renovação em 13/12/2018. No dia seguinte, o Réu negou condicionadamente — exigindo a apresentação de Termo de Compromisso assinado (CAEAI e CACS). A obra, que em novembro/2018 estava com 92,06% de execução, foi forçosamente paralisada.",
    "Em 13/01/2019, o Réu lavrou o Auto de Embargo por execução de obra sem alvará válido. As Autoras tiveram que conceder férias coletivas e suportar custos de mão de obra e locação de equipamentos sem contrapartida produtiva. Os custos diários de R$ 5.606,18 resultaram em prejuízo de R$ 95.305,06 nos 17 dias de paralisação forçada.",
  ],
  callout: "A paralisação ameaçava diretamente os contratos de financiamento com a CEF: atrasos superiores a 6 meses implicariam absorção de encargos pela construtora, com risco de R$ 2,4 milhões.",
});
addDocSlide({ ponto: "Ponto 4", title: "2a Grave Ilegalidade — Negativa do Alvará, Embargo e Paralisação", isAlert: true, docs: ["Doc. 13  9719672604 — Negativa do Alvará", "Doc. 14  9719672605 — Auto de Embargo", "Doc. 27  9719678657 — Resumo custos Mão de Obra", "Doc. 28  9719678658 — Extratos CAGED", "Doc. 29  9719678659 — Recibos de Férias", "Doc. 30  9719678660 — Boleto Unimed", "Doc. 31  9719678661 — Seguro de Vida em Grupo", "Doc. 32  9719678662 — Boleto PCMSO", "Doc. 33  9719678663 — Resumo custos Locações", "Doc. 34  9719678664 — Contrato Plataforma Elevatória 10m", "Doc. 35  9719678665 — Contrato Plataforma Elevatória 12m", "Doc. 36  9719678666 — Contrato Paleteira", "Doc. 37  9719678667 — Contrato Formas", "Doc. 38  9719678668 — Contrato Container", "Doc. 39  9719678669 — Serviços de Segurança", "Doc. 40  9719678670 — Ata Notarial", "Doc. 45  9719683307 — Medição da Obra (nov/2018)", "Doc. 45A  9719683308 — Fotos da Obra (dez/2018)", "Doc. 46  9719683309 — Ata de Assembleia de Condomínio", "Doc. 46A  9719683310 — Fotos da Assembleia"] });

// PONTO 5
addSectionSlide({
  pontoLabel: "PONTO 5 — COAÇÃO ADMINISTRATIVA E ASSINATURA FORÇADA DO TAM",
  title: "Mandado de Segurança, desistência sob pressão e TAM das caçambas (jan–fev/2019)",
  period: "jan–fev/2019", isAlert: true,
  paragraphs: [
    "Diante das ilegalidades, as Autoras impetraram o MS no 5024229-88.2018.8.13.0027 em 17/12/2018, questionando as exigências como ilegais e inconstitucionais. O Réu, mesmo assim, em 11/01/2019, notificou as Autoras para assinar o Termo de Implantação das Medidas CAEAI em 5 dias, sob pena de invalidade, e simultaneamente autorizou o início da obra de canalização da Av. Miosótis.",
    "Em 22/01/2019, o Réu emitiu novo Alvará Provisório no 8/2019 com prazo de apenas 30 dias (até 22/02/2019) para assinatura do TAM. Coagidas pela ameaça concreta de paralisação definitiva e perda do financiamento da CEF, as Autoras assinaram em 07/02/2019 o Termo de Ajustamento Municipal, comprometendo-se a doar 320 caçambas de resíduos sólidos avaliadas em R$ 1.177.600,00 — e desistiram do Mandado de Segurança.",
  ],
  callout: "O TAM condicionou a emissão do habite-se à entrega das caçambas e à desistência da ação judicial — caracterizando coação administrativa com vício de consentimento (REsp 237.583/PR).",
});
addDocSlide({ ponto: "Ponto 5", title: "Coação Administrativa e TAM das Caçambas", isAlert: true, docs: ["Doc. 15  9719672606 — Notificação p/ assinatura Termo CAEAI", "Doc. 16  9719672607 — Autorização início obra CAEAI", "Doc. 17  9719672608 — Alvará provisório 30 dias", "Doc. 22  9719678652 — Novo Termo de Compromisso CAEAI", "Doc. 23  9719678653 — Termo de Ajustamento Municipal (TAM)", "Doc. 47  9719683311 — Precedente REsp 237.583/PR", "Doc. 48  9719683312 — Inicial do MS 5024229-88.2018", "Doc. 48A  9719683313 — Desistência do MS"] });

// PONTO 6
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.accentLight }, line: { color: C.accentLight } });
  s.addText("PONTO 6 — 3a GRAVE ILEGALIDADE: CUSTO EXCEDENTE NA CONTRAPARTIDA CAEAI", { x: 0.25, y: 0.22, w: 9.5, h: 0.32, fontSize: 8.5, color: C.accentLight, charSpacing: 2, fontFace: "Georgia" });
  s.addText("Obra viária com estouro de orçamento além do limite fixado (2018–2019)", { x: 0.25, y: 0.52, w: 9.5, h: 0.65, fontSize: 17, bold: true, color: C.ink, fontFace: "Georgia" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 1.2, w: 1.6, h: 0.3, fill: { color: C.tagBg }, line: { color: C.tagBg } });
  s.addText("2018–2019", { x: 0.25, y: 1.2, w: 1.6, h: 0.3, fontSize: 9, color: C.accent, align: "center", fontFace: "Calibri" });
  s.addText("A contrapartida CAEAI consistia na canalização de trecho da Avenida Miosótis. O custo havia sido fixado pelo próprio Réu em R$ 1.571.429,92. Contudo, a execução real resultou em custo total de R$ 1.836.838,75 — um excedente de R$ 265.408,77 (mais precisamente R$ 219.654,57 em serviços extras).", { x: 0.25, y: 1.62, w: 9.5, h: 0.65, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addText("O estouro não decorreu de decisão voluntária das Autoras. Elas foram coagidas a executar as obras nos termos exigidos pelo Réu — inclusive por força da Notificação do Doc. 15, que as obrigou à assinatura do Doc. 22, pelo qual a Requerida as compeliu a elaborar e aprovar todos os projetos executivos e a executar as obras de ligação proposta sob responsabilidade e custo exclusivos das Autoras.", { x: 0.25, y: 2.35, w: 9.5, h: 0.88, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addText("O Município recebeu e quitou a obra em 06/09/2019, reconhecendo sua execução conforme projeto e encerrando as obrigações da construtora perante o CAEAI. O valor excedente foi suportado pelas Autoras em violação direta ao compromisso firmado em 2016.", { x: 0.25, y: 3.32, w: 9.5, h: 0.55, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 3.98, w: 9.5, h: 0.55, fill: { color: C.callout }, line: { color: C.accentLight } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 3.98, w: 0.06, h: 0.55, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("Docs. 15 e 22 — Notificação CAEAI  |  Doc. 25 — Contrato e orçamento Obra CAEAI  |  Doc. 26 — Termo de Recebimento e quitação CAEAI", { x: 0.42, y: 4.03, w: 9.2, h: 0.45, fontSize: 9, italic: true, color: C.accent, fontFace: "Calibri", valign: "middle" });
}
addDocSlide({ ponto: "Ponto 6", title: "3a Grave Ilegalidade — Custo Excedente na Contrapartida CAEAI", isAlert: true, docs: ["Doc. 15  9719672606 — Notificação p/ assinatura Termo CAEAI", "Doc. 22  9719678652 — Novo Termo de Compromisso CAEAI", "Doc. 25  9719678655 — Contrato e orçamento Obra CAEAI", "Doc. 26  9719678656 — Termo de Recebimento e quitação CAEAI"] });

// PONTO 7
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.muted }, line: { color: C.muted } });
  s.addText("PONTO 7 — CUMPRIMENTO, CONCLUSÃO E APURAÇÃO DOS DANOS", { x: 0.25, y: 0.22, w: 9.5, h: 0.32, fontSize: 8.5, color: C.muted, charSpacing: 2, fontFace: "Georgia" });
  s.addText("Entrega do empreendimento, quitação das caçambas e montante de danos (2019)", { x: 0.25, y: 0.52, w: 9.5, h: 0.65, fontSize: 17, bold: true, color: C.ink, fontFace: "Georgia" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 1.2, w: 1.0, h: 0.3, fill: { color: C.tagBg }, line: { color: C.tagBg } });
  s.addText("2019", { x: 0.25, y: 1.2, w: 1.0, h: 0.3, fontSize: 9, color: C.accent, align: "center", fontFace: "Calibri" });
  s.addText("As 320 caçambas foram entregues entre fevereiro e maio de 2019, com recebimento pelo Município (ECOS) em 03/06/2019, ao valor total de R$ 1.056.000,00. O habite-se parcial residencial foi emitido em 15/05/2019 e o habite-se parcial das 25 lojas em 10/10/2019. O empreendimento foi integralmente entregue em 12/06/2019.", { x: 0.25, y: 1.62, w: 9.5, h: 0.65, fontSize: 10, color: "2e2520", fontFace: "Calibri", lineSpacingMultiple: 1.3, valign: "top" });
  const damages = [
    { label: "Contrapartida Social (caçambas)", value: "R$ 1.177.600,00", date: "a partir de 07/02/2019", note: "(i)" },
    { label: "Excedente contrapartida CAEAI", value: "R$ 265.408,77", date: "a partir de 06/09/2019", note: "(ii)" },
    { label: "17 dias de paralisação ilegal", value: "R$ 95.305,06", date: "a partir de 13/01/2019", note: "(iii)" },
  ];
  damages.forEach((d, i) => {
    const x = 0.25 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.42, w: 3.0, h: 1.55, fill: { color: C.highlight }, line: { color: C.tagBg }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.42, w: 3.0, h: 0.1, fill: { color: C.accentLight }, line: { color: C.accentLight } });
    s.addText(d.note, { x: x + 0.1, y: 2.52, w: 0.3, h: 0.3, fontSize: 9, color: C.muted, fontFace: "Calibri" });
    s.addText(d.label, { x: x + 0.1, y: 2.52, w: 2.8, h: 0.38, fontSize: 9.5, bold: true, color: C.accent, fontFace: "Georgia", valign: "middle" });
    s.addText(d.value, { x: x + 0.1, y: 2.96, w: 2.8, h: 0.45, fontSize: 14, bold: true, color: C.ink, fontFace: "Georgia" });
    s.addText(d.date, { x: x + 0.1, y: 3.45, w: 2.8, h: 0.3, fontSize: 8.5, italic: true, color: C.muted, fontFace: "Calibri" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 4.1, w: 9.5, h: 0.8, fill: { color: C.accent }, line: { color: C.accent }, shadow: makeShadow() });
  s.addText("MONTANTE TOTAL DE DANOS", { x: 0.4, y: 4.15, w: 5, h: 0.35, fontSize: 9, color: C.tagBg, charSpacing: 3, fontFace: "Georgia" });
  s.addText("R$ 1.538.313,83", { x: 0.4, y: 4.45, w: 5, h: 0.38, fontSize: 20, bold: true, color: C.white, fontFace: "Georgia" });
  s.addText("+ correção monetária + juros de mora de 1% ao mês", { x: 5.2, y: 4.32, w: 4.4, h: 0.5, fontSize: 9.5, italic: true, color: C.tagBg, fontFace: "Calibri", valign: "middle" });
}
addDocSlide({ ponto: "Ponto 7", title: "Cumprimento, Conclusão e Apuração dos Danos (2019)", isAlert: false, docs: ["Doc. 20  9719672612 — Habite-se parcial (residencial)", "Doc. 21  9719672613 — Habite-se parcial (25 lojas)", "Doc. 24  9719678654 — Termo de Recebimento TAM (caçambas)"] });

// SLIDE FINAL
{
  let s = pres.addSlide();
  s.background = { color: C.accent };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.muted }, line: { color: C.muted } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.12, w: 10, h: 0.03, fill: { color: C.muted }, line: { color: C.muted } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.06, fill: { color: C.muted }, line: { color: C.muted } });
  s.addText("Síntese dos Danos", { x: 0.5, y: 0.7, w: 9, h: 0.55, fontSize: 28, bold: true, color: C.white, align: "center", fontFace: "Georgia" });
  const rows = [
    ["Contrapartida Social (caçambas) — TAM forçado", "R$ 1.177.600,00", "Ponto 5"],
    ["Excedente contrapartida CAEAI — estouro orçamentário", "R$ 265.408,77", "Ponto 6"],
    ["Paralisação ilegal da obra — 17 dias", "R$ 95.305,06", "Ponto 4"],
  ];
  rows.forEach((row, i) => {
    const y = 1.45 + i * 0.82;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 9.2, h: 0.68, fill: { color: "1d4438" }, line: { color: C.muted } });
    s.addText(row[0], { x: 0.6, y: y + 0.12, w: 6.2, h: 0.42, fontSize: 11, color: C.tagBg, fontFace: "Calibri" });
    s.addText(row[1], { x: 6.85, y: y + 0.1, w: 2.0, h: 0.45, fontSize: 13, bold: true, color: C.white, fontFace: "Georgia", align: "right" });
    s.addShape(pres.shapes.RECTANGLE, { x: 9.0, y: y + 0.14, w: 0.55, h: 0.38, fill: { color: C.accentLight }, line: { color: C.accentLight } });
    s.addText(row[2], { x: 9.0, y: y + 0.14, w: 0.55, h: 0.38, fontSize: 7.5, color: C.white, fontFace: "Calibri", align: "center", valign: "middle" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 3.95, w: 9.2, h: 0.72, fill: { color: C.white }, line: { color: C.white } });
  s.addText("TOTAL", { x: 0.6, y: 4.05, w: 3, h: 0.52, fontSize: 13, bold: true, color: C.accent, fontFace: "Georgia" });
  s.addText("R$ 1.538.313,83", { x: 3.6, y: 4.0, w: 5.8, h: 0.6, fontSize: 22, bold: true, color: C.accent, fontFace: "Georgia", align: "right" });
  s.addText("+ correção monetária e juros de mora de 1% ao mês sobre cada parcela", { x: 0.5, y: 4.82, w: 9, h: 0.32, fontSize: 9, italic: true, color: C.tagBg, fontFace: "Calibri", align: "center" });
  s.addText("Residencial Barcelona Incorporações SPE Ltda. e Construtora Você Eireli  v.  Município de Betim\nAção Ordinária — Vara Empresarial, Fazenda Pública e Autarquias — Comarca de Betim/MG", { x: 0.5, y: 5.1, w: 9, h: 0.45, fontSize: 8.5, italic: true, color: C.tagBg, fontFace: "Calibri", align: "center" });
}

pres.writeFile({ fileName: "barcelona.pptx" })
  .then(() => console.log("barcelona.pptx gerado com sucesso!"))
  .catch(err => { console.error("Erro:", err); process.exit(1); });
