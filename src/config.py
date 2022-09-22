#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

""" Bot Configuration """


class DefaultConfig:
    """ Bot Configuration """
    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")


""" GPT-3 Configuration """


class GPT3Config:
    """ Configuration for OpenAI GPT3 API Call"""
    endpoint = "https://testrrm.openai.azure.com/openai/deployments/generate_response/completions?api-version=2022-06-01-preview"
    MODEL = "text-davinci-002"
    temperature = 0.0
    max_tokens = 60
    top_p = 1.0
    frequency_penalty = 0.0
    presence_penalty = 0.0
    best_of = 3
    task = 'tl;dr:'


""" Pre-processing Configuration"""


class PreprocessingConfig:
    """ Configuration for Text Preprocessing """
    text_truncation_chars = 3000

class PathConfig:
    folder_path = "/Users/yiranliu/Library/CloudStorage/OneDrive-Microsoft/Hackathon/Nuen/Nuen-Bot-Test/"
    preprocess_txt_folder = "processed_text_files/"
    preprocess_txt = "condensed_Transcript_4.txt"
    api_response_csv = "api_response/api_response.csv"
