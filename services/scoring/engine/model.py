# ----------------------------------------------------------------------------
# Score Engine - LegalScore PJ
# MLR custom por CNAE de 2 digitos
# ----------------------------------------------------------------------------



class LegalScoreModel:
    def __init__(self, cnae_2digit: str):
        self.cnae = cnae_2digit
        self.coefficients = self._load_coefficients(cnae_2digit)

    def _load_coefficients(self, cnae_2digit: str) -> dict[str, float]:
        # TODO: carregar coeficientes calibrados via Delphi method + dados publicos
        return {
            "intercept": 500,
            "processos_ativos": -2.5,
            "processos_trabalhistas": -3.0,
            "divida_ativa_valor_log": -12.0,
            "divida_ativa_crescimento": -8.0,
            "saldo_emprego_12m": 1.2,
            "capital_social_log": 15.0,
            "processos_repetitivos": -5.0,
        }

    def predict(self, features: dict) -> dict:
        score = self.coefficients["intercept"]
        feature_names = [
            "processos_ativos",
            "processos_trabalhistas",
            "divida_ativa_valor_log",
            "divida_ativa_crescimento",
            "saldo_emprego_12m",
            "capital_social_log",
            "processos_repetitivos",
        ]

        for name in feature_names:
            score += self.coefficients.get(name, 0) * features.get(name, 0)

        score_normalized = max(0, min(1000, int(score)))
        ci_lower, ci_upper = self._bootstrap_ci(features, n=1000)

        return {
            "score": score_normalized,
            "confidence_interval": [ci_lower, ci_upper],
            "risk_level": self._classify_risk(score_normalized),
            "dimension_breakdown": self._get_breakdown(features),
        }

    def _bootstrap_ci(self, features: dict, n: int = 1000):
        # TODO: implementar bootstrap na Fase 1
        return [max(0, 450), min(1000, 550)]

    def _classify_risk(self, score: int) -> str:
        if score >= 800:
            return "BAIXO"
        if score >= 600:
            return "MODERADO"
        if score >= 400:
            return "ALTO"
        return "CRITICO"

    def _get_breakdown(self, features: dict) -> dict:
        # TODO: calcular contribuicao por dimensao
        return {
            "juridico": 0.4,
            "financeiro": 0.35,
            "trabalhista": 0.15,
            "setorial": 0.10,
        }
