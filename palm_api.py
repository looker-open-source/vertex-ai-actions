import os
import vertexai
from vertexai.preview.language_models import TextGenerationModel


def predict_llm(
    temperature: float,
    max_output_tokens: int,
    top_k: int,
    top_p: float,
    content: str,
    model_name: str = 'text-bison@001',  # todo parameterise model type on form
):
    """Predict using a Large Language Model."""

    vertexai.init(project=os.environ.get('PROJECT'),
                  location=os.environ.get('REGION'))
    model = TextGenerationModel.from_pretrained(model_name)

    response = model.predict(
        content,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        top_k=top_k,
        top_p=top_p,)
    print('Response from Model: {}'.format(response))
    return response
