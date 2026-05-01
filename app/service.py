import joblib
import pandas as pd
import os
from .utils import process_credit_features, get_decision_thresholds

class CreditScoringService:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        modelo_path = os.path.join(base_dir, 'models', 'modelo_payflow_v1.pkl')
        colunas_path = os.path.join(base_dir, 'models', 'colunas_modelo.pkl')
        
        if not os.path.exists(modelo_path):
            raise FileNotFoundError(f"Modelo não encontrado em: {modelo_path}")
            
        self.modelo = joblib.load(modelo_path)
        self.colunas = joblib.load(colunas_path)

    def process_features(self, req):
        req_dict = req.model_dump() if hasattr(req, 'model_dump') else (req.dict() if hasattr(req, 'dict') else req)
        return process_credit_features(req_dict, self.colunas)

    def predict(self, req):
        df_model, comprometimento = self.process_features(req)
        probabilidade = self.modelo.predict_proba(df_model)[0][1]
        
        thresholds = get_decision_thresholds()
        
        if probabilidade < thresholds["RISCO_BAIXO_MAX"]:
            decisao = "APROVAR"
            msg = "Risco classificado como BAIXO."
        elif probabilidade < thresholds["RISCO_MEDIO_MAX"]:
            decisao = "REVISAR"
            msg = "Atenção: Risco MÉDIO detectado. Revisão manual necessária."
        else:
            decisao = "NEGAR"
            msg = "Alerta: Risco ALTO de inadimplência."
            
        return probabilidade, decisao, comprometimento, msg
