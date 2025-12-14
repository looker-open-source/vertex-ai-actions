import backoff
import ratelimit
import os
import vertexai
import logging
from vertexai.generative_models import GenerationConfig, GenerativeModel
from google.api_core import exceptions

MODEL_VARIANT = os.environ.get('MODEL_VARIANT', 'gemini-2.5-flash')
CALL_LIMIT = int(os.environ.get('CALL_LIMIT', '50'))  # Number of calls to allow within a period
ONE_MINUTE = int(os.environ.get('ONE_MINUTE', '60'))  # One minute in seconds
FIVE_MINUTE = 5 * ONE_MINUTE


initial_prompt_template = '''
    I am an analyst using a business intelligence tool to prompt AI to derive insights on my data.
    I will create queries to ask different questions about my first-party data.
    This may include sales data, customer data, marketing data, retention data, internal HR data, etc.
    I will provide you the results of these queries in the form of a JSON payload.
    Responses should be comprehensive with different metrics, insights and inferences made about the data.
    Please include insights that would be difficult to capture by the naked eye reading a chart or data table. 
    Answer my question below in following text based on the JSON payload delimited by triple backquotes:
    
    Question:

    ```{question}```
    
    JSON payload: 
    
    ```{data}```

    Answer:
'''


final_prompt_template = '''
    Write a very concise summary of the following text delimited by triple backquotes.
    Return your response in 3-5 short bullet points which cover the key points of the text.
    Keep it brief and to the point.

    ```{text}```

    BRIEF SUMMARY:
'''


def backoff_hdlr(details):
    """function to print a message when the function is retrying"""
    logging.warning('Backing off {} seconds after {} tries'.format(
        details['wait'], details['tries']))


@backoff.on_exception(  # Retry with exponential backoff strategy when exceptions occur
    backoff.expo,
    (
        exceptions.ResourceExhausted,
        ratelimit.RateLimitException,
    ),  # Exceptions to retry on
    max_time=FIVE_MINUTE,
    on_backoff=backoff_hdlr,  # Function to call when retrying
)
@ratelimit.limits(  # Limit the number of calls to the model per minute
    calls=CALL_LIMIT, period=ONE_MINUTE
)
def model_prediction(model: GenerativeModel,
                     content: str,
                     temperature: float,
                     max_output_tokens: int,
                     top_k: int,
                     top_p: float,
                     ):
    """Predict using a Large Language Model."""
    config = GenerationConfig(max_output_tokens=max_output_tokens,
                              temperature=temperature, top_p=top_p, top_k=top_k)
    response = model.generate_content(content, generation_config=config)
    logging.info('Response from model: {}'.format(response))
    return response


def model_with_limit_and_backoff(all_data: dict,
                                 question: str,
                                 row_chunks: int,
                                 temperature: float,
                                 max_output_tokens: int,
                                 top_k: int,
                                 top_p: float,
                                 model_name: str
                                 ):
    """Split data into chunks to call model predict function and applies rate limiting."""
    vertexai.init(project=os.environ.get('PROJECT'),
                  location=os.environ.get('REGION'))
    model = GenerativeModel(model_name)
    initial_summary = []
    list_size = len(all_data)

    # max input token [text-bison: 8192, code-bison: 6144] so we split data into chunks
    for i in range(0, list_size, row_chunks):
        chunk = all_data[i:i+row_chunks]
        logging.info('Processing rows {} to {}.'.format(i, i+row_chunks))
        content = initial_prompt_template.format(question=question, data=chunk)
        summary = model_prediction(
            model, content, temperature, max_output_tokens, top_k, top_p).text
        initial_summary.append(summary)  # append summary to list of summaries

    return initial_summary


def reduce(initial_summary: any,
           temperature: float,
           max_output_tokens: int,
           top_k: int,
           top_p: float,
           model_name: str
           ):
    """creates a summary of the summaries"""

    vertexai.init(project=os.environ.get('PROJECT'),
                  location=os.environ.get('REGION'))
    model = GenerativeModel(model_name)
    content = final_prompt_template.format(text=initial_summary)

    # Generate a summary using the model and the prompt
    summary = model_prediction(
        model, content, temperature, max_output_tokens, top_k, top_p).text

    return summary
