import os
import sys
import requests
import json
import concurrent.futures
import enum

POST = 1
GET = 0
MANGADEX = "https://api.mangadex.org"
REPORT = "https://api.mangadex.network"
TAG_DICT = dict()
TAG_AND = "AND"
TAG_OR = "OR"
ONESHOT_CHAPTER = -1

class Status(enum.Enum):
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_HIATUS = "hiatus"
    STATUS_CANCELLED = "cancelled"

class Content(enum.Enum):
    SAFE = ['safe']
    SUGGESTIVE = ['safe', 'suggestive']
    EROTICA = ['safe', 'suggestive', 'erotica']
    PORNOGRAPHIC = ['safe', 'suggestive', 'erotica', 'pornographic']

class MultiChapterTranslations(enum.IntEnum):
    MOST_PROLIFIC_GROUP_EVERY_CHAPTER = 0
    ANY_GROUP_EVERY_CHAPTER = 1
    EVERY_CHAPTER_AND_TRANSLATION = 2


def __MD_get_img_extension(link: str):
    period_index = link.rfind('.')

    if period_index == -1:
        return None

    return link[period_index:]


def __MD_check_status_code(status_code: int, allowable_codes=None):

    if allowable_codes is not None and isinstance(allowable_codes, list):
        if status_code in allowable_codes:
            return

    if status_code == 200:
        return
    elif status_code == 204:
        print(f"API request -- Code:[{status_code}] Empty Response")
        return
    elif status_code == 400:
        sys.exit(f"API request failed -- Code:[{status_code}] bad request")
    elif status_code == 401:
        sys.exit(f"API request failed -- Code:[{status_code}] unauthorized to access. Login maybe?")
    elif status_code == 403:
        sys.exit(f"API request failed -- Code:[{status_code}] forbidden resource requested")
    elif status_code == 404:
        sys.exit(f"API request failed -- Code:[{status_code}] Page not found")
    elif status_code == 429:
        sys.exit(f"API request failed -- Code:[{status_code}] too many requests")
    elif status_code == 503:
        sys.exit(f"API request failed -- Code:[{status_code}] service unavailable")
    else:
        sys.exit(f"API request failed -- Code:[{status_code}] unknown response code")


def api_request(request_type: int, api_site: str, endpoint: str, parameters="", payload=None, headers=None, log=False):
    if log:
        print("Sending api request")

    return_var = None
    if request_type == GET:
        return_var = requests.get(api_site + endpoint + parameters, data=payload, headers=headers)
    elif request_type == POST:
        return_var = requests.post(api_site + endpoint + parameters, data=payload, headers=headers)

    if log:
        print("api response received")

    __MD_check_status_code(return_var.status_code)

    return return_var


def __MD_create_login_header(token_response: str):
    token_string = json.loads(token_response)['token']['session']
    return {'Authorization': 'Bearer ' + token_string}


def setup_tag_dict():
    json_tags = json.loads(api_request(GET, MANGADEX, "/manga/tag").content)

    for tag in json_tags:
        name = tag['data']['attributes']['name']['en']
        TAG_DICT[name] = tag['data']['id']


def get_login_header(username, password, log=False):
    login_payload = json.dumps({'username': username, 'password': password})

    if log:
        print("logging in")

    login_response = api_request(POST, MANGADEX, "/auth/login", payload=login_payload)

    if log:
        print("logged in")

    return __MD_create_login_header(login_response.text)


def check_logged_in(__auth_header, log=False):
    if log:
        print("checking if logged in")

    cli_response = api_request(GET, MANGADEX, "/auth/check", headers=__auth_header)

    if log:
        print("login check successful")

    return True


def __MD_send_data_to_md(manga_page_response):
    cached = bool()
    if manga_page_response.headers['X-Cache'] == 'MISS':
        cached = False
    elif manga_page_response.headers['X-Cache'] == 'HIT':
        cached = True
    else:
        print(manga_page_response.headers)
        sys.exit("Error: When attempting to send data, encountered an X-Cache which was not MISS or HIT")

    feedback_data = {'url': manga_page_response.url, 'success': True, 'bytes': len(manga_page_response.content),
                     'duration': manga_page_response.elapsed.microseconds // 1000, 'cached': cached}
    feedback_data = json.dumps(feedback_data)

    # DEBUG
    # print(feedback_data)
    # with open("out_test_data.json", 'w') as output_file:
    #    json.dump(feedback_data, output_file, indent=2)

    response = api_request(POST, REPORT, "/report", payload=feedback_data)
    return


def find_chapter_home(chapter_id: str, forcePort443=True):
    forcePort443_param = ""
    if forcePort443 is False:
        forcePort443_param = "?forcePort443=false"
    else:
        forcePort443_param = "?forcePort443=true"

    athome_response = api_request(GET, MANGADEX, "/at-home/server/" + chapter_id, parameters=forcePort443_param)

    athome_json = json.loads(athome_response.text)
    return athome_json['baseUrl']


def fetch_manga_page(img_base_url: str, image_name: str, report_data=True, file_path="", log: bool = True):


    # img_base_url includes the chapter home, quality, and chapter hash
    full_url = img_base_url + image_name

    if log:
        pass
        # print(f"Downloading {image_name}")

    response = api_request(GET, full_url, "")

    if file_path != "":
        with open(file_path, 'wb') as out_file:
            out_file.write(response.content)

    if report_data is True:
        __MD_send_data_to_md(response)

    return


# folder path takes path to the folder with no slash after it
def download_manga_chapter(chapter_id, folder_path: str, data_saver: bool = False):
    chapter_response = api_request(GET, MANGADEX, f"/chapter/{chapter_id}")

    chapter_json = json.loads(chapter_response.text)
    home_url = find_chapter_home(chapter_id)
    if data_saver is False:
        img_base_url = home_url + "/data/" + chapter_json['data']['attributes']['hash'] + '/'
    else:
        img_base_url = home_url + "/data-saver/" + chapter_json['data']['attributes']['hash'] + '/'

    # print(f"Downloading {chapter_json['data']}\nTo dir {folder_path}")
    with open("chapter_JSON.json", 'w') as out_file:
        json.dump(chapter_json, out_file, indent=2)

    if not os.path.isdir(folder_path):
        os.mkdir(folder_path)

    if data_saver is False:
        chapter_image_list = chapter_json['data']['attributes']['data']
    else:
        chapter_image_list = chapter_json['data']['attributes']['dataSaver']

    image_pool_data = []
    page_number = 1
    for image in chapter_image_list:
        image_pool_data.append((image, page_number))
        page_number += 1

    download_image = lambda image_data: fetch_manga_page(img_base_url, image_data[0],
                                                         file_path=folder_path + "/pg" + str(image_data[1]) + __MD_get_img_extension(image_data[0]))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_image, image_pool_data)

    return


def get_complete_json_feed(manga_id: str, log: bool = False):
    """
    This returns a complete feed of ALL chapter objects for a given manga in the form of a JSON object which
    is an array of chapter objects. This function DOES NOT filter by language or remove chapter duplicates.
    get_final_chapter_list_from_json() is the function which does that
    """

    limit = 500  # maximum amount of chapter objects which will be received from one API request
    offset = 0

    # returns the feed of chapters for a manga from the api request as a JSON object
    def get_feed(__limit, __offset): return json.loads(
        api_request(GET, MANGADEX, "/manga/" + manga_id + "/feed", f"?limit={__limit}&offset={__offset}").content)

    # get the first 500 feed chapters. This also tells us how many total feed chapter items we will need in total
    feed = get_feed(limit, offset)
    total_feed_chapters = feed['total']
    feed = feed['results']

    if log:
        print("Initial chapter feed fetched")

    # if more feeds need to be fetched, do this multithreaded in case there are multiple requests needed
    if total_feed_chapters > limit:
        offset_list = list()
        limit_list = list()

        while total_feed_chapters > offset + limit:
            offset += limit
            offset_list.append(offset)
            limit_list.append(limit)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            additional_feeds = executor.map(get_feed, limit_list, offset_list)

        for new_feed in additional_feeds:
            feed += new_feed['results']

    # THIS CODE WAS USED BEFORE. DELETE IF THIS WORKS WITHOUT ISSUES
    #while total_feed_chapters > limit + offset:
    #    offset += limit
    #    feed += get_feed(limit, offset)['results']  # add the new chapters to the feed
    #    if log:
    #        print("More chapters fetched for feed")

    # THIS WAS A DEBUG STATEMENT TO ENSURE THE NEW VERSION WORKS. DELETE IF THIS WORKS WITHOUT ISSUES
    # print(f"Return feed has {len(feed)} items")

    return feed


def chapter_num_to_float(convert_num):
    try:
        return float(convert_num)
    except:
        return ONESHOT_CHAPTER


def get_final_chapter_list_from_json(json_feed, language: str = "en",
                                     multipleChapterTranslations: MultiChapterTranslations = MultiChapterTranslations.MOST_PROLIFIC_GROUP_EVERY_CHAPTER):
    """
    This function returns a list of tuples containing the data needed to download a chapter
    These tuples are also sorted according to parameters i.e. strip out all of the chapters with different languages,
    only pick the chapters with the most popular scanlator groups (this is default behavior which can be modified
    via a parameter), and put the chapters in order

    Tuples are (chapter_id, chapter_no, scanlator_group)
    """

    # remove chapters of different language and populate the scanlator list (used for comparing number of chapters translated per group)
    chapter_list = list()
    scanlator_list = dict()
    scanlator_list[None] = 0

    for chapter in json_feed:
        if chapter['data']['attributes']['translatedLanguage'] == language:
            chapter_data = [chapter['data']['id'], chapter['data']['attributes']['chapter']]

            # Add to the tally of how many chapters each scanlation group has done for this particular manga
            for relationship in chapter['relationships']:
                if relationship['type'] == 'scanlation_group':
                    scanlator_list[relationship['id']] = scanlator_list.get(relationship['id'], 0) + 1
                    chapter_data.append(relationship['id'])
                    break

            # I have no idea if a chapter can have no registered translation group
            # so this will be left in for now to catch that if it happens
            if len(chapter_data) == 2:
                raise Exception(f"Chapter encountered without scanlator group\n{chapter}")
                # chapter_data.append(None)

            chapter_list.append(chapter_data)

    # float because there can be chapters such as 12.5 - Negative 1 in the case chapter has no number (Oneshot)
    chapter_list.sort(key=lambda data: chapter_num_to_float(data[1]))

    # trim out extra chapters picking the most popular scanlator for each chapter
    # TODO add other selection criteria for scanlation groups. E.G. downloading all translations of a chapter
    trimmed_chapter_list = list()
    i = 0
    while i < len(chapter_list):
        end_index = i + 1
        while end_index < len(chapter_list) and chapter_list[i][1] == chapter_list[end_index][1]:
            end_index += 1

        # TODO this is the line where we would add if statements to
        chapter_data_insert = max(chapter_list[i:end_index], key=lambda data: scanlator_list[data[2]])

        trimmed_chapter_list.append(chapter_data_insert)
        i = end_index

    return trimmed_chapter_list


def download_manga(manga_id: str, dirpath: str = None, data_saver: bool = False, language: str = "en",
                   multipleChapterTranslations: MultiChapterTranslations = MultiChapterTranslations.MOST_PROLIFIC_GROUP_EVERY_CHAPTER
                   , log: bool = False):
    if log:
        print("Starting manga download")

    # Get manga name for directory if no name provided
    if dirpath is None:
        response = api_request(GET, MANGADEX, "/manga/" + manga_id)
        manga_feed = json.loads(response.content)
        dirpath = manga_feed['data']['attributes']['title']['en']
    if log:
        print(f"Downloading manga {manga_id} to dir {dirpath}")

    # Get the list of manga chapters
    chapter_list = get_final_chapter_list_from_json(
        get_complete_json_feed(manga_id), language=language, multipleChapterTranslations=multipleChapterTranslations)
    if log:
        print("Finished downloading feed")

    # Setup download directory
    if os.path.isdir(dirpath):
        raise Exception(f"Duplicate Directory found. Directory is {dirpath}")
    else:
        os.mkdir(dirpath)

    # download oneshot
    if len(chapter_list) == 1 and chapter_list[0][1] == ONESHOT_CHAPTER:
        download_manga_chapter(chapter_list[0][0], dirpath, data_saver=data_saver)

    # download chaptered series
    else:

        # download manga chapter
        for i, chapter in enumerate(chapter_list):
            print(f"Downloading progress:{i + 1}/{len(chapter_list)} - Chapter Number:{chapter[1]}")

            chapter_dir = dirpath + "/Chap_" + chapter[1]
            if os.path.isdir(chapter_dir):
                if not multipleChapterTranslations:
                    raise Exception(f"Duplicate chapter found. Directory is {chapter_dir}")
                else:
                    chapter_dir += "_dup_1"
                    while os.path.isdir(chapter_dir):
                        j = chapter_dir.rfind('_')
                        chapter_dir = chapter_dir[:j] + str((int(chapter_dir[j:]) + 1))

            os.mkdir(chapter_dir)

            download_manga_chapter(chapter[0], chapter_dir, data_saver=data_saver)

    if log:
        print(f"Manga download finished - {manga_id}")


def search_manga(title: str, limit=10, included_tags: list[str] = None, includedTagsMode: str = None,
                 excluded_tags: list[str] = None, excludedTagsMode: str = None, contentRating: list[str] = ['safe', 'suggestive']):

    params = f"?title={title}&limit={limit}"

    if included_tags is not None:
        for tag_name in included_tags:
            if tag_name in TAG_DICT:
                params += f"&includedTags[]={TAG_DICT[tag_name]}"

    if includedTagsMode is not None:
        params += f"&includedTagsMode={includedTagsMode}"

    if excluded_tags is not None:
        for tag_name in excluded_tags:
            if tag_name in TAG_DICT:
                params += f"&excludedTags[]={TAG_DICT[tag_name]}"

    if excludedTagsMode is not None:
        params += f"&excludedTagsMode={excludedTagsMode}"

    if contentRating is not None:
        for content in contentRating:
            params += f"&contentRating[]={content}"

    # parameter setup finished. Send request

    search_response = api_request(GET, MANGADEX, '/manga', parameters=params)
    print(params)
    print(search_response)
    print(search_response.text)
    if search_response.status_code == 204:
        return list()
    else:
        json_data = json.loads(search_response.text)
        return_list = list()
        for manga in json_data['results']:
            tuple_left = manga['data']['attributes']['title']
            tuple_right = manga['data']['attributes']['altTitles']
            tuple_id = manga['data']['id']
            if len(tuple_right) > 0:
                tuple_right = tuple_right[0]
            else:
                tuple_right = None
            return_list.append((tuple_left, tuple_right, tuple_id))

        return return_list


def print_tag_dict(num_per_line: int = 5):

    tags = [tag for tag in TAG_DICT]

    index = 0
    while index + num_per_line <= len(tags):
        print(tags[index:index + num_per_line])
        index += num_per_line

    print(tags[index:])




if __name__ == "__main__":

    setup_tag_dict()

    while 1:
        commands = input("S for search. T to see list of tags. Q to quit\n").lower().split(' ')

        if commands[0] == "s":
            search = input('Example search.\nname=[Fullmetal Alchemist] itags=[Romance,Comedy] etags=[Oneshot] lim=[20]\n')
            s_name = None
            s_itags = None
            s_etags = None
            s_lim = 10

            start_index = 0
            while start_index < len(search):
                print(f"starting from index {start_index} which is {search[start_index]}")
                eq_index = search.find('=', start_index)
                param = search[start_index:eq_index]
                lbrack_index = search.find('[', eq_index)
                rbrack_index = search.find(']', lbrack_index)
                args = search[lbrack_index+1:rbrack_index]

                print(f"param is {param} args is {args}")
                if param == "name":
                    s_name = args
                elif param == "itags":
                    s_itags = args.split(',')
                elif param == "etags":
                    s_etags = args.split(',')
                elif param == "lim":
                    s_lim = int(args)

                start_index = search.find(' ', rbrack_index, len(search) - 1) + 1
                if start_index < eq_index:
                    start_index = 999999999999999

            print("This is where we would search")
            print(f"searching: s_name:{s_name}, s_itags:{s_itags}, s_etags:{s_etags}, s_lim:{s_lim}")
            search_results = search_manga(s_name, limit=s_lim, included_tags=s_itags, excluded_tags=s_etags)

            if search_results is not None:
                for index, result in enumerate(search_results):
                    print(f"{index}:{result}")

                download_input = input("Download a manga from the results? Enter the number for yes, n for no\n").lower()
                if download_input.isnumeric():
                    download_index = int(download_input)
                    if len(search_results) > download_index >= 0:
                        download_manga(search_results[download_index][2])

        elif commands[0] == "t":
            print_tag_dict()
        elif commands[0] == "q":
            exit()

