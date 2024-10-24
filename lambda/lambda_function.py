import json
import boto3
import logging
import random
import base64
import io
import os

# Define Logger
logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

sagemaker_client = boto3.client("sagemaker-runtime")


def update_seed(prompt_dict, seed=None):
    """
    Update the seed value for the KSampler node in the prompt dictionary.

    Args:
        prompt_dict (dict): The prompt dictionary containing the node information.
        seed (int, optional): The seed value to set for the KSampler node. If not provided, a random seed will be generated.

    Returns:
        dict: The updated prompt dictionary with the seed value set for the KSampler node.
    """
    # set seed for KSampler node
    for i in prompt_dict:
        if "inputs" in prompt_dict[i]:
            if (
                prompt_dict[i]["class_type"] == "KSampler"
                and "seed" in prompt_dict[i]["inputs"]
            ):
                if seed is None:
                    prompt_dict[i]["inputs"]["seed"] = random.randint(0, int(1e10))
                else:
                    prompt_dict[i]["inputs"]["seed"] = int(seed)
    return prompt_dict


def update_prompt_text(prompt_dict, positive_prompt, negative_prompt):
    """
    Update the prompt text in the given prompt dictionary.

    Args:
        prompt_dict (dict): The dictionary containing the prompt information.
        positive_prompt (str): The new text to replace the positive prompt placeholder.
        negative_prompt (str): The new text to replace the negative prompt placeholder.

    Returns:
        dict: The updated prompt dictionary.
    """
    # replace prompt text for CLIPTextEncode node
    for i in prompt_dict:
        if "inputs" in prompt_dict[i]:
            if (
                prompt_dict[i]["class_type"] == "CLIPTextEncode"
                and "text" in prompt_dict[i]["inputs"]
            ):
                if prompt_dict[i]["inputs"]["text"] == "POSITIVE_PROMT_PLACEHOLDER":
                    prompt_dict[i]["inputs"]["text"] = positive_prompt
                elif prompt_dict[i]["inputs"]["text"] == "NEGATIVE_PROMPT_PLACEHOLDER":
                    prompt_dict[i]["inputs"]["text"] = negative_prompt
    return prompt_dict

import base64
def encode_binary_to_base64(binary_image):
    return base64.b64encode(binary_image).decode('utf-8')

def prepare_payload_with_binary_images(existing_payload, binary_images):
    # Encode and add to dictionary
    encoded_images = {}
    for i, binary_image in enumerate(binary_images):
        encoded_images[f"image_{i}"] = encode_binary_to_base64(binary_image)

    # Update the existing payload with the encoded images
    existing_payload.update({"images": encoded_images})
    return json.dumps(existing_payload)

def invoke_from_prompt(prompt_file, positive_prompt, negative_prompt, seed=None, images):
    """
    Invokes the SageMaker endpoint with the provided prompt data.

    Args:
        prompt_file (str): The path to the JSON file in ./workflow/ containing the prompt data.
        positive_prompt (str): The positive prompt to be used in the prompt data.
        negative_prompt (str): The negative prompt to be used in the prompt data.
        seed (int, optional): The seed value for randomization. Defaults to None.

    Returns:
        dict: The response from the SageMaker endpoint.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    logger.info("prompt: %s", prompt_file)

    # read the prompt data from json file
    with open("./workflow/" + prompt_file) as prompt_file:
        prompt_text = prompt_file.read()

    prompt_dict = json.loads(prompt_text)
    prompt_dict = update_seed(prompt_dict, seed)
    prompt_dict = update_prompt_text(prompt_dict, positive_prompt, negative_prompt)

    endpoint_name = os.environ["ENDPOINT_NAME"]
    content_type = "application/json"
    accept = "*/*"
    # The images are already in base64 as they were accessed through a json file
    # Assuming it is setup such that images in already encoded as base64 and is a dictionary with the encoded image
    prompt_dict.update({"images": images})
    payload = json.dumps(prompt_dict)
    logger.info("Final payload to invoke sagemaker:")
    logger.info(json.dumps(payload, indent=4))
    response = sagemaker_client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType=content_type,
        Accept=accept,
        Body=payload,
    )
    return response


def lambda_handler(event: dict, context: dict):
    """
    Lambda function handler for processing events.

    Args:
        event (dict): The event from lambda function URL.
        context (dict): The runtime information of the Lambda function.

    Returns:
        dict: The response data for lambda function URL.
    """
    logger.info("Event:")
    logger.info(json.dumps(event, indent=2))
    request = json.loads(event["body"])

    try:
        positive_prompt = request["positive_prompt"]
        negative_prompt = request.get("negative_prompt", "")
        seed = request.get("seed")
        # Assuming it is setup such that images in already encoded as base64 and is a dictionary with the encoded image
        images = request.get("images",{})
        prompt_file = f"workflow_api_{len(images)}person_api.json"
        response = invoke_from_prompt(
            prompt_file=prompt_file,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            imgaes=images,
        )
    except KeyError as e:
        logger.error(f"Error: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": "Missing required parameter",
                }
            ),
        }

    image_data = response["Body"].read()

    result = {
        "headers": {"Content-Type": response["ContentType"]},
        "statusCode": response["ResponseMetadata"]["HTTPStatusCode"],
        "body": base64.b64encode(io.BytesIO(image_data).getvalue()).decode("utf-8"),
        "isBase64Encoded": True,
    }
    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    event = {
        "body": "{\"positive_prompt\": \"hill happy dog\",\"negative_prompt\": \"hill\",\"prompt_file\": \"workflow_api.json\",\"seed\": 123}"
    }
    lambda_handler(event, None)
