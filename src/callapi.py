import requests
import json
import pandas as pd
from config import GPT3Config, PreprocessingConfig, PathConfig
import os
import re
import urllib

def remove_tags(text):
    """
    Remove vtt markup tags
    """
    tags = [
        r'</c>',
        r'<c(\.color\w+)?>',
        r'<\d{2}:\d{2}:\d{2}\.\d{3}>',
    ]
    for pat in tags:
        text = re.sub(pat, '', text)

    # extract timestamp, only kep HH:MM
    text = re.sub(
        r'(\d{2}:\d{2}):\d{2}\.\d{3} --> .* align:start position:0%',
        r'\g<1>',
        text
    )

    text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)
    return text


def remove_header(lines):
    """
    Remove vtt file header
    """
    pos = -1
    for mark in ('##', 'Language: en',):
        if mark in lines:
            pos = lines.index(mark)
    lines = lines[pos + 1:]
    return lines


def merge_duplicates(lines):
    """
    Remove duplicated subtitles. Duplicates are always adjacent.
    """
    last_timestamp = ''
    last_cap = ''
    for line in lines:
        if line == "":
            continue
        if re.match('^\d{2}:\d{2}$', line):
            if line != last_timestamp:
                yield line
                last_timestamp = line
        else:
            if line != last_cap:
                yield line
                last_cap = line


def merge_short_lines(lines):
    buffer = ''
    for line in lines:
        if line == "" or re.match('^\d{2}:\d{2}$', line):
            yield '\n' + line
            continue

        if len(line + buffer) < 80:
            buffer += ' ' + line
        else:
            yield buffer.strip()
            buffer = line
    yield buffer


def text_preprocessing(line):
    STOPWORDS = ["WEBVTT", "ï»¿WEBVTT", "<v"]
    x = line.split(" ")
    x = [re.sub("\d+:\d+:\d+.\d+", "", token) for token in x if token != "-->"]
    x = [token.replace("</v>", "").replace(">", " ") for token in x if len(token) != 0]
    x = [token for token in x if "/" not in token and token not in STOPWORDS]
    return " ".join(x)


def preprocess_text(input_text):
    """
    Preprocess the input text
    """
    config = PreprocessingConfig()
    text = remove_tags(input_text)
    text = truncate_text(text, num_chars=config.text_truncation_chars)
    lines = text.splitlines()
    lines = remove_header(lines)
    lines = [text_preprocessing(line) for line in lines]
    lines = merge_duplicates(lines)
    lines = list(lines)
    lines = merge_short_lines(lines)
    lines = list(lines)
    lines = [line for line in lines if len(line) != 0]
    return lines


def truncate_text(input_text, num_chars=3000):
    """
    Truncate input_text to num_words words
    """
    if num_chars < len(input_text):
        print(f"Truncating text from {len(input_text)} to {num_chars} characters")
    return input_text[:num_chars]


def get_download_url(turn_context):
    if turn_context and turn_context.activity and turn_context.activity.attachments \
            and len(turn_context.activity.attachments) > 0:
        for attachment in turn_context.activity.attachments:
            # 1:1 chat in teams
            if hasattr(attachment, 'content') and attachment.content and type(attachment.content) == dict:
                if attachment.content['fileType'] and attachment.content['fileType'] == 'vtt':
                    if attachment.content['downloadUrl']:
                        return attachment.content['downloadUrl']
            # web chat
            elif attachment.content_type == 'text/vtt':
                return attachment.content_url
    return None


def read_data(download_url):
    response = urllib.request.urlopen(download_url)
    raw_text = response.read()
    return raw_text.decode("utf-8")


def parse_vtt(input_text):
    batches = []
    current_speaker = ''
    current_text = ''
    for line in input_text.split('\n'):
        x = re.findall("<v (.*)>(.*)</v>", line)
        if x:
            if len(current_text.split()) + len(x[0][1].split()) > 2500:
                batches.append(current_text)
                current_speaker = ''
                current_text = ''
            if x[0][0] == current_speaker:
                current_text = ' '.join([current_text, x[0][1]])
            else:
                current_speaker = x[0][0]
                if current_text != '':
                    current_text = current_text + '\n'
                current_text = current_text + current_speaker + ': ' + x[0][1]
    if current_speaker != '':
        batches.append(current_text)

    return batches

def call_openai_api(text, task):
    """
    Call Open AI GPT-3 API on input text for a particular task, e.g. 'Tl;dr' or 'TODO Action Item'
    """
    config = GPT3Config()
    endpoint = config.endpoint
    headers = {
            "api-key": os.environ['OPENAI_API_KEY']
          }
    data = {
              "prompt": f"{text}\n\n{task}",
              "temperature": config.temperature,
              "top_p": config.top_p,
              "frequency_penalty": config.frequency_penalty,
              "presence_penalty": config.presence_penalty,
              "best_of": config.best_of,
              "max_tokens": config.max_tokens,
              "stop": None
            }
    response = requests.post(endpoint, data=json.dumps(data).encode(encoding='utf-8'), headers=headers)
    ans_dict = json.loads(response.text.rstrip())
    ans = ans_dict['choices'][0]['text'].strip()
    return ans

def call_openai_api_in_batches(batches, task):
    full_text = ''
    for text in batches:
        full_text = full_text + "\n\n" + call_openai_api(text, task)
        # print(f"TEXT\n{text}\n\nAPI RESPONSE\n{full_text}\n***********\n")
    return full_text

def post_process_summary(raw_summary):
    return raw_summary.replace("\n", "\n\n")


def post_process_actions(raw_actions):
    split_text = re.split(r'- |\[\s]|[0-9]*\.|\n', raw_actions)
    return '\n\n'.join(['- ' + x for x in split_text if x.strip() != ''])


def compare_response():
    path_config = PathConfig()
    config = GPT3Config()
    preprocessing_config = PreprocessingConfig()
    with open(path_config.folder_path + path_config.preprocess_file_folder + path_config.preprocess_file) as f:
        text = f.read()
    text_batches = parse_vtt(text)
    raw_summary = call_openai_api_in_batches(text_batches, 'tl;dr:')
    raw_actions = call_openai_api_in_batches(text_batches, 'TODO Action items:')
    summary = post_process_summary(raw_summary)
    actions = post_process_actions(raw_actions)
    # print(f"{summary}/n{actions}")
    df = pd.read_csv(path_config.folder_path + path_config.api_response_csv)
    data = pd.DataFrame({"txt_file_name": path_config.preprocess_file,
                            "temperature": config.temperature,
                            "top_p": config.top_p,
                            "frequency_penalty": config.frequency_penalty,
                            "presence_penalty": config.frequency_penalty,
                            "summary": str(summary.replace("\n\n", "\n")),
                            "actions": str(actions.replace("\n\n", "\n"))}, index=[0])
    df = df.append(data, ignore_index=True)
    df.to_csv(path_config.folder_path + path_config.api_response_csv, index=False)

if __name__ == "__main__":
    compare_response()
