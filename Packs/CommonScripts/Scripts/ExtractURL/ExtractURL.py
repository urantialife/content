from html import unescape
from typing import Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs, ParseResult, unquote
from urllib.request import urlopen

from CommonServerPython import *

ATP_REGEX = re.compile(r'(https://\w*|\w*)\.safelinks\.protection\.outlook\.com/.*\?url=')
PROOF_POINT_URL_REG = re.compile(r'https://urldefense(?:\.proofpoint)?\.(com|us)/(v[0-9])/')
HTTP = 'http'
PREFIX_TO_NORMALIZE = {
    'hxxp',
    'meow',
    'hXXp',
}
# Tuple of starts_with, does_not_start_with (if exists), replace to.
PREFIX_CHANGES: List[Tuple[str, Optional[str], str]] = [
    ('https:/', 'https://', 'https://'),
    ('http:/', 'http://', 'http://'),
    ('https:\\', 'https:\\\\', 'https://'),
    ('http:\\', 'http:\\\\', 'http://'),
    ('https:\\\\', None, 'https://'),
    ('http:\\\\', None, 'http://')
]


def get_redirect_url_proof_point_v2(non_formatted_url: str, parse_results: ParseResult) -> str:
    """
    Extracts redirect URL from Proof Point V2.
    Args:
        non_formatted_url (str): Non formatted URL.
        parse_results (ParseResult): Parse results of the given URL.

    Returns:
        (str): Redirected URL from Proof Point.
    """
    url_: str = get_redirect_url_from_query(non_formatted_url, parse_results, 'u')
    trans = str.maketrans('-_', '%/')
    url_ = url_.translate(trans)
    return url_


def get_redirect_url_proof_point_v3(non_formatted_url: str) -> str:
    """
    Extracts redirect URL from Proof Point V3.
    Args:
        non_formatted_url (str): Non formatted URL.

    Returns:
        (str): Redirected URL from Proof Point.
    """
    url_regex = re.compile(r'v3/__(?P<url>.+?)__;(?P<enc_bytes>.*?)!')
    if match := url_regex.search(non_formatted_url):
        non_formatted_url = match.group('url')
    else:
        demisto.error(f'Could not parse Proof Point redirected URL. Returning original URL: {non_formatted_url}')
    return non_formatted_url


def get_redirect_url_from_query(non_formatted_url: str, parse_results: ParseResult, redirect_param_name: str) -> str:
    """
    Receives an ATP Safe Link URL, returns the URL the ATP Safe Link points to.
    Args:
        non_formatted_url (str): The raw URL. For debugging purposes.
        parse_results (str): ATP Safe Link URL parse results.
        redirect_param_name (str): Name of the redirect parameter.
    Returns:
        (str): The URL the ATP Safe Link points to.
    """
    query_params_dict: Dict[str, List[str]] = parse_qs(parse_results.query)
    if not (query_urls := query_params_dict.get(redirect_param_name, [])):
        demisto.error(f'Could not find redirected URL. Returning the original URL: {non_formatted_url}')
        return non_formatted_url
    if len(query_urls) > 1:
        demisto.debug(f'Found more than one URL query parameters for redirect in the given URL {non_formatted_url}\n'
                      f'Returning the first URL: {query_urls[0]}')
    url_: str = query_urls[0]
    return url_


def replace_protocol(url_: str) -> str:
    """
    Replaces URL protocol with expected protocol. Examples can be found in tests.
    Args:
        url_ (str): URL to replace the protocol by the given examples above.

    Returns:
        (str): URL with replaced protocol, if needed to replace, else the URL itself.
    """
    for prefix_to_normalize in PREFIX_TO_NORMALIZE:
        if url_.startswith(prefix_to_normalize):
            url_ = url_.replace(prefix_to_normalize, HTTP)
    lowercase_url = url_.lower()
    for starts_with, does_not_start_with, to_replace in PREFIX_CHANGES:
        if lowercase_url.startswith(starts_with) and (
                not does_not_start_with or not lowercase_url.startswith(does_not_start_with)):
            url_ = url_.replace(starts_with, to_replace)
    return url_


def format_url(non_formatted_url: str) -> str:
    """
    Formats a single URL.
    Args:
        non_formatted_url (str): Non formatted URL.

    Returns:
        (Set[str]): Formatted URL, with its expanded URL if such exists.
    """
    parse_results: ParseResult = urlparse(non_formatted_url)
    if re.match(ATP_REGEX, non_formatted_url):
        non_formatted_url = get_redirect_url_from_query(non_formatted_url, parse_results, 'url')
    elif match := PROOF_POINT_URL_REG.search(non_formatted_url):
        proof_point_ver: str = match.group(2)
        if proof_point_ver == 'v3':
            non_formatted_url = get_redirect_url_proof_point_v3(non_formatted_url)
        elif proof_point_ver == 'v2':
            non_formatted_url = get_redirect_url_proof_point_v2(non_formatted_url, parse_results)
        else:
            non_formatted_url = get_redirect_url_from_query(non_formatted_url, parse_results, 'u')
    # Common handling for unescape and normalizing
    non_formatted_url = unquote(unescape(non_formatted_url.replace('[.]', '.')))
    formatted_url = replace_protocol(non_formatted_url)
    return formatted_url


def expand_url(formatted_url: str) -> Set[str]:
    """
    Expands given URL. Returns a set of one URL if the URL is not a shorten URL, else returns shorten URL and
    its expanded URL as a set.
    Args:
        formatted_url (set): URL.

    Returns:
        (Set[str]): Set of URL, and its expanded URL if such exists and is different than the given URL.
    """
    try:
        expanded_url: str = urlopen(formatted_url, timeout=1).url
        return {formatted_url, expanded_url}
    # In case expanded URL is broken or does not exist anymore
    except (HTTPError, ValueError, URLError):
        pass
    return {formatted_url}


def main():
    try:
        demisto.results(format_url(expand_url(demisto.args().get('input'))))
    except Exception as e:
        demisto.error(traceback.format_exc())  # print the traceback
        return_error(f'Failed to execute ExtractURL. Error: {str(e)}')


''' ENTRY POINT '''

if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
