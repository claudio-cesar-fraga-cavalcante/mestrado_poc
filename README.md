# Validador Neuro-Simbólico de Editais (Lei nº 13.303/2016 + Ontologia UFO-L)

PoC de Mestrado para auditoria automatizada e explicável de editais de licitação de empresas públicas e sociedades de economia mista (Lei nº 13.303/2016), combinando:
- **Camada Neural (Google Gemini / Structured Outputs):** Extração semântica de fatos observáveis e evidências literais a partir do texto do edital (`.txt`).
- **Camada Simbólica (Prolog + Ontologia Jurídica UFO-L):** Raciocínio deôntico/relacional baseado nas posições fundamentais de Hohfeld e Alexy (`duty_to_act`, `duty_to_omit`, `permission_to_act`, `permission_to_omit`, `power`, `disability`, `immunity`).
- **Camada de Explicabilidade (Streamlit):** Geração de pareceres fundamentados com a árvore de derivação lógica (SLD-Resolution), citação exata da linha do edital e referência ao dispositivo da Lei 13.303/2016.

## Estrutura do Projeto

- `app.py`: Interface web interativa em Streamlit.
- `src/`:
  - `parser_edital.py`: Segmentação e indexação linha a linha de editais `.txt` e dos artigos da Lei 13.303/2016.
  - `extractor_llm.py`: Extrator ontológico (Modo Demonstração Offline e Modo Live via Google Gemini) e tradutor para fatos Prolog (ABox).
  - `ufo_l_rules.pl`: Formalização das regras da Lei 13.303/2016 sobre a ontologia núcleo `UFO_L.pl`.
  - `reasoner_prolog.py`: Motor de inferência SLD ISO-Prolog com rastreamento de prova formal (e integração com `swipl`).
  - `explainer.py`: Consolidador de pareceres jurídicos auditáveis e exportação JSON.
- `dados/`:
  - `L13303.txt`: Texto integral da Lei nº 13.303/2016.
  - `regras_validador.json` / `regras_validador.csv`: Catálogo de 80 regras extraídas da Lei 13.303/2016.
  - `UFO_L.pl`: Axiomatização em Prolog da ontologia núcleo jurídica UFO-L.
  - `Edital_PE_29-2026.txt`: Edital real (BNDES - Contratação de DaaS).
  - `editais_teste/`: Editais sintéticos/mutacionados para validação cruzada.

## Como Executar

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```
