from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from pymongo import MongoClient
from dataclasses import dataclass, asdict
import random
from datetime import datetime, timedelta
import pickle
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()


bairro_coords = {
    "Centro": [-23.5505, -46.6333],
    "Bairro A": [-23.55, -46.65],
    "Bairro B": [-23.52, -46.66],
    "Zona Rural": [-23.6, -46.7]
}

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["meu_banco"]
colecao = db["meus_dados"]

class Vitima:
    etnia: str
    idade: int
    sexo: str  
 
 

@dataclass
class Caso:
    data_do_caso: str
    tipo_do_caso: str
    localizacao: str
    vitima: Vitima

    def to_dict(self):
        return {
            "data_do_caso": self.data_do_caso,
            "tipo_do_caso": self.tipo_do_caso,
            "localizacao": self.localizacao,
            "vitima": asdict(self.vitima)
        }

def gerar_dados_aleatorios(n=20):
    tipos_casos = ["Furto", "Assalto", "Violência Doméstica", "Tráfico"]
    locais = ["Centro", "Bairro A", "Bairro B", "Zona Rural"]
    etnias = ["Branca", "Preta", "Parda", "Amarela", "Indígena"]
    sexos = ["masculino", "feminino"]
    casos = []
    base_date = datetime.now()
    for _ in range(n):
        data_do_caso = (base_date - timedelta(days=random.randint(0, 365))).date().isoformat()
        caso = Caso(
            data_do_caso=data_do_caso,
            tipo_do_caso=random.choice(tipos_casos),
            localizacao=random.choice(locais),
            vitima=Vitima(
                etnia=random.choice(etnias),
                idade=random.randint(1, 90),
                sexo=random.choice(sexos)
            )
        )
        casos.append(caso.to_dict())
    return casos

def validar_caso_json(data):
    try:
        vitima = data['vitima']
        assert isinstance(vitima, dict)
        assert all(k in vitima for k in ['etnia', 'idade', 'sexo'])
        datetime.fromisoformat(data['data_do_caso'])
        assert isinstance(data['tipo_do_caso'], str)
        assert isinstance(data['localizacao'], str)
    except:
        return False
    return True

@app.route('/')
def hello():
    return "Bem vindo à API de análise de casos criminais"

@app.route('/api/stats/localizacoes', methods=['GET'])
def distribuicao_localizacoes():
    dados = list(colecao.find({}, {"_id": 0, "localizacao": 1}))
    pontos = []
    for doc in dados:
        bairro = doc.get("localizacao")
        coords = bairro_coords.get(bairro)
        if coords:
            pontos.append({"bairro": bairro, "lat": coords[0], "lon": coords[1]})
    return jsonify(pontos)


@app.route('/api/casos', methods=['GET'])
def listar_casos():
    query = {}

    # Filtro por sexo (se estiver presente no JSON do MongoDB)
    if 'sexo' in request.args and request.args['sexo'] != 'todos':
        query["vitima.sexo"] = request.args["sexo"]

    # Filtro por etnia
    if 'etnia' in request.args and request.args['etnia'] != 'todos':
        query["vitima.etnia"] = request.args["etnia"]

    # Filtro por idade mínima e máxima
    if 'idadeMin' in request.args or 'idadeMax' in request.args:
        idade_query = {}
        if 'idadeMin' in request.args:
            idade_query["$gte"] = int(request.args["idadeMin"])
        if 'idadeMax' in request.args:
            idade_query["$lte"] = int(request.args["idadeMax"])
        query["vitima.idade"] = idade_query

    # Filtro por data_do_caso (intervalo de datas)
    if 'dataInicio' in request.args or 'dataFim' in request.args:
        data_query = {}
        if 'dataInicio' in request.args:
            data_query["$gte"] = request.args["dataInicio"]
        if 'dataFim' in request.args:
            data_query["$lte"] = request.args["dataFim"]
        query["data_do_caso"] = data_query

    documentos = list(colecao.find(query, {"_id": 0}))
    return jsonify(documentos), 200

@app.route('/api/casos', methods=['POST'])
def criar_caso():
    data = request.json
    if not data or not validar_caso_json(data):
        abort(400, "JSON inválido ou campos faltando")
    colecao.insert_one(data)
    return jsonify({"message": "Caso criado com sucesso"}), 201

@app.route('/api/casos/<string:data_caso>', methods=['GET'])
def buscar_caso(data_caso):
    caso = colecao.find_one({"data_do_caso": data_caso}, {"_id": 0})
    if not caso:
        abort(404, "Caso não encontrado")
    return jsonify(caso), 200

@app.route('/api/casos/<string:data_caso>', methods=['DELETE'])
def deletar_caso(data_caso):
    resultado = colecao.delete_one({"data_do_caso": data_caso})
    if resultado.deleted_count == 0:
        abort(404, "Caso não encontrado")
    return jsonify({"message": "Caso deletado com sucesso"}), 200

@app.route('/api/stats/idades', methods=['GET'])
def distribuicao_idades():
    dados = list(colecao.find({}, {"_id": 0, "vitima.idade": 1}))
    idades = [doc['vitima']['idade'] for doc in dados if 'vitima' in doc and 'idade' in doc['vitima']]
    return jsonify(idades)

@app.route('/api/stats/boxplot-sexo', methods=['GET'])
def boxplot_sexo():
    dados = list(colecao.find({}, {"_id": 0}))
    registros = []
    for d in dados:
        sexo = d.get("vitima", {}).get("sexo")
        idade = d.get("vitima", {}).get("idade")
        tipo = d.get("tipo_do_caso")
        if sexo and idade is not None and tipo:
            registros.append({
                "sexo": sexo,
                "idade": idade,
                "tipo_do_caso": tipo
            })
    return jsonify(registros)

with open("model.pkl", "rb") as f:
    data = pickle.load(f)
    modelo = data["pipeline"]
    label_encoder = data["label_encoder"]
    modelo_acuracia = data.get("accuracy", None)

@app.route('/api/predizer', methods=['POST'])
def predizer():
    dados = request.get_json()
    if not dados or not all(k in dados for k in ["idade", "etnia", "localizacao"]):
        return jsonify({"erro": "JSON inválido. Esperado: idade, etnia, localizacao"}), 400
    try:
        df = pd.DataFrame([dados])
        print("🔍 Dados recebidos:")
        print(df)

        y_prob = modelo.predict_proba(df)[0]
        y_pred_encoded = modelo.predict(df)[0]
        y_pred = label_encoder.inverse_transform([y_pred_encoded])[0]
        classes = label_encoder.classes_

        resultado = {
            "classe_predita": y_pred,
            "probabilidades": {
                classe: round(float(prob), 4)  # <- conversão aqui
                for classe, prob in zip(classes, y_prob)
            }
        }

        return jsonify(resultado), 200

    except Exception as e:
        import traceback
        print("❌ ERRO NA PREDIÇÃO:")
        print(traceback.format_exc())
        return jsonify({"erro": f"Erro ao fazer predição: {str(e)}"}), 500

@app.route('/api/modelo/coefs', methods=['GET'])
def coeficientes_modelo():
    try:
        preprocessor = modelo.named_steps['preprocessor']
        classifier = modelo.named_steps['classifier']
        cat_encoder = preprocessor.named_transformers_['cat']
        cat_features = cat_encoder.get_feature_names_out(preprocessor.transformers_[0][2])
        numeric_features = preprocessor.transformers_[1][2]
        all_features = list(cat_features) + list(numeric_features)
        importancias = classifier.feature_importances_
        features_importances = {feature: float(importance) for feature, importance in zip(all_features, importancias)}
        return jsonify(features_importances), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/modelo/probabilidade-idade', methods=['GET'])
def probabilidade_por_idade():
    try:
        sexo = request.args.get("sexo")
        etnia = request.args.get("etnia")
        idade_min = request.args.get("idadeMin", type=int)
        idade_max = request.args.get("idadeMax", type=int)
        data_inicio = request.args.get("dataInicio")
        data_fim = request.args.get("dataFim")

        # Use esses filtros para ajustar as entradas simuladas
        faixas = [(0, 18), (19, 30), (31, 45), (46, 60), (61, 100)]
        resultados = []
        localizacao_padrao = "Centro"

        for faixa in faixas:
            idade_media = sum(faixa) // 2
            entrada = {
                "idade": idade_media,
                "etnia": etnia if etnia and etnia != "todos" else random.choice(["Branca", "Preta", "Parda"]),
                "localizacao": localizacao_padrao
            }

            df = pd.DataFrame([entrada])
            probs = modelo.predict_proba(df)[0]
            resultado = {
                "faixa": f"{faixa[0]}-{faixa[1]}",
                "probabilidades": {
                    classe: round(float(prob), 4) for classe, prob in zip(label_encoder.classes_, probs)
                }
            }
            resultados.append(resultado)

        return jsonify(resultados)

    except Exception as e:
        import traceback
        print("❌ Erro interno:", traceback.format_exc())
        return jsonify({"erro": f"Erro: {str(e)}"}), 500

@app.route('/api/modelo/correlacoes', methods=['GET'])
def correlacoes():
    try:
        dados = list(colecao.find({}, {"_id": 0}))
        df = pd.DataFrame(dados)
        df["tipo_do_caso_codificado"] = label_encoder.transform(df["tipo_do_caso"])
        df["idade"] = df["vitima"].apply(lambda x: x.get("idade") if isinstance(x, dict) else None)
        correl = df[["idade", "tipo_do_caso_codificado"]].dropna()
        valor = round(float(correl.corr().iloc[0, 1]), 4)
        return jsonify({
            "variaveis": ["idade", "tipo_do_caso_codificado"],
            "matriz": [[1.0, valor], [valor, 1.0]]
        })
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)}"}), 500

@app.route('/api/modelo/acuracia', methods=['GET'])
def obter_acuracia():
    try:
        query = {}

        # Filtro por sexo (caso exista no documento)
        sexo = request.args.get("sexo")
        if sexo and sexo != "todos":
            query["vitima.sexo"] = sexo

        etnia = request.args.get("etnia")
        if etnia and etnia != "todos":
            query["vitima.etnia"] = etnia

        # Idade
        idade_query = {}
        idade_min = request.args.get("idadeMin")
        idade_max = request.args.get("idadeMax")
        if idade_min:
            idade_query["$gte"] = int(idade_min)
        if idade_max:
            idade_query["$lte"] = int(idade_max)
        if idade_query:
            query["vitima.idade"] = idade_query

        # Datas
        data_query = {}
        data_inicio = request.args.get("dataInicio")
        data_fim = request.args.get("dataFim")
        if data_inicio:
            data_query["$gte"] = data_inicio
        if data_fim:
            data_query["$lte"] = data_fim
        if data_query:
            query["data_do_caso"] = data_query

        dados = list(colecao.find(query, {"_id": 0}))
        if not dados:
            return jsonify({"classes": [], "precisao": []})

        df = pd.DataFrame([{
            "idade": d.get("vitima", {}).get("idade"),
            "etnia": d.get("vitima", {}).get("etnia"),
            "localizacao": d.get("localizacao"),
            "tipo_do_caso": d.get("tipo_do_caso")
        } for d in dados]).dropna()

        X = df[["idade", "etnia", "localizacao"]]
        y = df["tipo_do_caso"]
        y_encoded = label_encoder.transform(y)
        y_pred = modelo.predict(X)
        classes = label_encoder.classes_

        precisao = []
        for i, classe in enumerate(classes):
            total = sum(y_encoded == i)
            corretos = sum((y_encoded == i) & (y_pred == i))
            acuracia_classe = (corretos / total) * 100 if total else 0
            precisao.append(round(acuracia_classe, 2))

        return jsonify({"classes": list(classes), "precisao": precisao})
    except Exception as e:
        import traceback
        print("❌ Erro na acurácia:", traceback.format_exc())
        return jsonify({"erro": str(e)}), 500
    

@app.route('/api/stats/pizza-tipo', methods=['GET'])
def distribuicao_tipo_caso():
    query = {}

    # Filtros opcionais
    sexo = request.args.get("sexo")
    if sexo and sexo != "todos":
        query["vitima.sexo"] = sexo

    etnia = request.args.get("etnia")
    if etnia and etnia != "todos":
        query["vitima.etnia"] = etnia

    idade_query = {}
    idade_min = request.args.get("idadeMin")
    idade_max = request.args.get("idadeMax")
    if idade_min:
        idade_query["$gte"] = int(idade_min)
    if idade_max:
        idade_query["$lte"] = int(idade_max)
    if idade_query:
        query["vitima.idade"] = idade_query

    data_query = {}
    data_inicio = request.args.get("dataInicio")
    data_fim = request.args.get("dataFim")
    if data_inicio:
        data_query["$gte"] = data_inicio
    if data_fim:
        data_query["$lte"] = data_fim
    if data_query:
        query["data_do_caso"] = data_query

    # Consulta ao MongoDB
    dados = list(colecao.find(query, {"_id": 0, "tipo_do_caso": 1}))
    contagem = {}
    for doc in dados:
        tipo = doc.get("tipo_do_caso")
        if tipo:
            contagem[tipo] = contagem.get(tipo, 0) + 1

    return jsonify(contagem)

    
if __name__ == '__main__':
    if colecao.count_documents({}) == 0:
        print("Inserindo dados iniciais...")
        dados_iniciais = gerar_dados_aleatorios(20)
        colecao.insert_many(dados_iniciais)
    app.run(debug=True)