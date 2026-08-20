import statistics
from dataclasses import dataclass


@dataclass
class TrendResult:
    status: str
    data_points: int
    trend_per_period: float | None
    projected_next_score: float | None


def compute_trend(scores_ordered: list[float]) -> TrendResult:
    """Tendência linear simples entre o primeiro e o último ponto histórico.

    `trend_per_period` = (último - primeiro) / número de intervalos entre os pontos.
    `projected_next_score` = último valor + `trend_per_period`, uma extrapolação ingênua
    de um período à frente. Precisa de ao menos 2 pontos com datas distintas; caso contrário
    o status é `insufficient_data` e nada é projetado.
    """
    if len(scores_ordered) < 2:
        return TrendResult(status="insufficient_data", data_points=len(scores_ordered), trend_per_period=None, projected_next_score=None)
    intervals = len(scores_ordered) - 1
    delta = scores_ordered[-1] - scores_ordered[0]
    trend_per_period = round(delta / intervals, 4)
    projected_next_score = round(scores_ordered[-1] + trend_per_period, 2)
    return TrendResult(status="estimate", data_points=len(scores_ordered), trend_per_period=trend_per_period, projected_next_score=projected_next_score)


@dataclass
class MarginResult:
    status: str
    reference_type: str
    reference_value: float | None
    margin: float | None


def compute_margin(user_score: float | None, reference_value: float | None, reference_type: str) -> MarginResult:
    """margin = nota estimada do usuário - valor de referência.

    A referência é `historical` quando existe uma `CutoffScore` oficial para este exame/cargo/
    categoria; `estimate` quando usamos a projeção de tendência de exames comparáveis; e
    `insufficient_data` quando não há nenhuma das duas. Sem nota estimada do usuário ou sem
    referência, o status é `insufficient_data` e `margin` fica nulo (nunca inventado).
    """
    if user_score is None or reference_value is None:
        return MarginResult(status="insufficient_data", reference_type=reference_type, reference_value=reference_value, margin=None)
    return MarginResult(status="estimate", reference_type=reference_type, reference_value=reference_value, margin=round(user_score - reference_value, 2))


@dataclass
class CompetitiveResult:
    status: str
    method: str | None
    index: float | None
    historical_mean: float | None
    historical_stdev: float | None


def compute_competitive_index(user_score: float | None, historical_scores: list[float]) -> CompetitiveResult:
    """Quantos desvios-padrão a nota estimada do usuário está da média das notas de corte comparáveis.

    `index = (user_score - média) / desvio_padrão_populacional` (`method = "z_score"`). Se o desvio
    padrão for zero (todas as notas de corte históricas iguais), cai para uma razão simples
    `user_score / média` (`method = "ratio_degenerate"`), pois z-score não é definível. Exige
    nota do usuário e ao menos 2 notas de corte históricas comparáveis; caso contrário,
    `insufficient_data`.
    """
    if user_score is None or len(historical_scores) < 2:
        return CompetitiveResult(status="insufficient_data", method=None, index=None, historical_mean=None, historical_stdev=None)
    mean = statistics.fmean(historical_scores)
    stdev = statistics.pstdev(historical_scores)
    if stdev > 0:
        index = round((user_score - mean) / stdev, 4)
        method = "z_score"
    else:
        index = round(user_score / mean, 4) if mean else None
        method = "ratio_degenerate"
    return CompetitiveResult(status="estimate", method=method, index=index, historical_mean=round(mean, 2), historical_stdev=round(stdev, 2))


def build_recommendations(user_score_status: str, margin: MarginResult, competitive: CompetitiveResult, subjects_without_data: list[str]) -> list[str]:
    """Recomendações determinísticas (não geradas por IA) derivadas dos números já calculados acima."""
    items: list[str] = []
    if user_score_status == "insufficient_data":
        items.append("Registre tentativas de questões ou simulados para calcularmos sua estimativa de nota.")
        return items
    if margin.status == "insufficient_data":
        items.append("Ainda não há nota de corte (própria ou de edições/bancas comparáveis) para comparar sua margem.")
    elif margin.margin < 0:
        items.append(f"Você está {abs(margin.margin):.2f} pontos abaixo da referência ({margin.reference_type}); priorize as disciplinas com menor acurácia.")
    elif margin.margin < 3:
        items.append(f"Margem apertada (+{margin.margin:.2f} sobre a referência {margin.reference_type}); mantenha o ritmo de revisões até a prova.")
    else:
        items.append(f"Margem confortável (+{margin.margin:.2f} sobre a referência {margin.reference_type}); foque em manter consistência.")
    if subjects_without_data:
        items.append("Sem dado de desempenho ainda em: " + ", ".join(subjects_without_data) + ".")
    if competitive.status == "estimate" and competitive.index is not None and competitive.method == "z_score":
        direction = "abaixo" if competitive.index < 0 else "acima"
        items.append(f"Seu desempenho estimado está {direction} da média histórica de notas de corte comparáveis ({competitive.index:+.2f} desvio-padrão).")
    return items
