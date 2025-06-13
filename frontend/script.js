document.addEventListener("DOMContentLoaded", () => {
  const fim = new Date();
  const inicio = new Date();
  inicio.setDate(inicio.getDate() - 30);
  document.getElementById("dataInicio").valueAsDate = inicio;
  document.getElementById("dataFim").valueAsDate = fim;

  carregarDados();
});

let dadosCasos = [],
  graficoRosca = null,
  graficoDistribuicao = null,
  graficoModelo = null;
const gradiente = [
  "#40516c",
  "#4a5d7c",
  "#53698c",
  "#5d759c",
  "#6b82a7",
  "#7b90b1",
  "#8b9dba",
];

function contarOcorrencias(dados, chave) {
  const contagem = {};
  dados.forEach((caso) => {
    const valor = chave.split(".").reduce((o, k) => o?.[k], caso);
    if (valor) contagem[valor] = (contagem[valor] || 0) + 1;
  });
  return contagem;
}

async function graficoProbabilidadePorIdade() {
  try {
    const res = await fetch(
      "http://localhost:5000/api/modelo/probabilidade-idade"
    );
    const dados = await res.json();

    const classes = Object.keys(dados[0].probabilidades);
    const labels = dados.map((d) => d.faixa);
    const datasets = classes.map((classe, idx) => ({
      label: classe,
      data: dados.map((d) => d.probabilidades[classe]),
      backgroundColor: gradiente[idx % gradiente.length],
      borderColor: gradiente[idx % gradiente.length],
      fill: false,
    }));

    const ctx = document.createElement("canvas");
    const div = document.createElement("div");
    div.classList.add("grafico-box");
    div.innerHTML = `<h3>Probabilidade do Tipo de Caso por Idade</h3>`;
    div.appendChild(ctx);
    document.body.appendChild(div);

    new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        scales: {
          y: {
            title: { display: true, text: "Probabilidade" },
            min: 0,
            max: 1,
          },
          x: {
            title: { display: true, text: "Faixa Etária" },
          },
        },
      },
    });
  } catch (e) {
    console.error("Erro no gráfico de probabilidade por idade:", e);
  }
}
async function graficoCorrelacoes() {
  try {
    const res = await fetch("http://localhost:5000/api/modelo/correlacoes");
    const { variaveis, matriz } = await res.json();

    const ctx = document.createElement("canvas");
    const div = document.createElement("div");
    div.classList.add("grafico-box");
    div.innerHTML = `<h3>Correlação entre Variáveis</h3>`;
    div.appendChild(ctx);
    document.body.appendChild(div);

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: variaveis,
        datasets: variaveis.map((_, i) => ({
          label: variaveis[i],
          data: matriz[i],
          backgroundColor: gradiente[i % gradiente.length],
        })),
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: "Correlação entre variáveis (coef. de Pearson)",
          },
        },
        scales: {
          y: { min: -1, max: 1 },
        },
      },
    });
  } catch (e) {
    console.error("Erro ao carregar gráfico de correlação:", e);
  }
}

async function graficoAcuraciaPorClasse() {
  try {
    const res = await fetch("http://localhost:5000/api/modelo/acuracia");
    const { classes, precisao } = await res.json();

    const ctx = document.createElement("canvas");
    const container = document.getElementById("graficoAcuracia");
    container.innerHTML = "";
    container.appendChild(ctx);

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: classes,
        datasets: [
          {
            label: "Acurácia (%)",
            data: precisao,
            backgroundColor: "#7b90b1",
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            title: { display: true, text: "Acurácia (%)" },
          },
        },
      },
    });
  } catch (e) {
    console.error("Erro ao carregar gráfico de acurácia por classe:", e);
  }
}

async function carregarDados() {
  try {
    const res = await fetch("http://localhost:5000/api/casos");
    dadosCasos = await res.json();
    atualizarGraficos();
    inicializarGraficoModelo();
    // Novos modelos aqui:
    graficoProbabilidadePorIdade();
    graficoCorrelacoes();
    graficoAcuraciaPorClasse();
  } catch (erro) {
    console.error("Erro ao carregar dados:", erro);
  }
}

function filtrarPorData(casos) {
  const inicio = document.getElementById("dataInicio").value;
  const fim = document.getElementById("dataFim").value;
  return casos.filter((caso) => {
    const data = new Date(caso.data_do_caso);
    return (
      (!inicio || data >= new Date(inicio)) && (!fim || data <= new Date(fim))
    );
  });
}

function atualizarGraficoRosca(dadosFiltrados) {
  const contagem = contarOcorrencias(dadosFiltrados, "tipo_do_caso");
  const ctx = document.createElement("canvas");
  const container = document.getElementById("graficoAcuracia");
  container.innerHTML = "";
  container.appendChild(ctx);
  if (graficoRosca) graficoRosca.destroy();

  graficoRosca = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: Object.keys(contagem),
      datasets: [
        {
          data: Object.values(contagem),
          backgroundColor: gradiente,
        },
      ],
    },
    options: { responsive: true },
  });
}

function atualizarGraficoDistribuicao(dadosFiltrados) {
  const idades = dadosFiltrados
    .map((c) => c.vitima?.idade)
    .filter((i) => i > 0);
  const bins = Array.from(
    { length: Math.ceil(Math.max(...idades, 100) / 10) },
    (_) => 0
  );
  idades.forEach((idade) => bins[Math.floor((idade - 1) / 10)]++);

  const labels = bins.map((_, i) => `${i * 10 + 1}-${(i + 1) * 10}`);

  const ctx = document.createElement("canvas");
  const container = document.getElementById("graficoAcuracia");
  container.innerHTML = "";
  container.appendChild(ctx);
  if (graficoDistribuicao) graficoDistribuicao.destroy();

  graficoDistribuicao = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Número de Vítimas",
          data: bins,
          backgroundColor: "#5d759c",
        },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true } },
    },
  });
}

async function inicializarGraficoModelo() {
  try {
    const res = await fetch("http://localhost:5000/api/modelo/coefs");
    const data = await res.json();
    const sorted = Object.entries(data).sort(
      (a, b) => Math.abs(b[1]) - Math.abs(a[1])
    );

    const ctx = document.createElement("canvas");
    const container = document.getElementById("graficoAcuracia");
    container.innerHTML = "";
    container.appendChild(ctx);
    if (graficoModelo) graficoModelo.destroy();

    graficoModelo = new Chart(ctx, {
      type: "bar",
      data: {
        labels: sorted.map(([k]) => k),
        datasets: [
          {
            label: "Importância",
            data: sorted.map(([, v]) => v),
            backgroundColor: "#5d759c",
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
      },
    });
  } catch (erro) {
    console.error("Erro ao carregar os coeficientes do modelo:", erro);
  }
}

document
  .getElementById("dataInicio")
  .addEventListener("change", atualizarGraficos);
document
  .getElementById("dataFim")
  .addEventListener("change", atualizarGraficos);

function atualizarGraficos() {
  const filtrados = filtrarPorData(dadosCasos);
  atualizarGraficoRosca(filtrados);
  atualizarGraficoDistribuicao(filtrados);
}
