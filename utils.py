import unicodedata
import string
import dash_html_components as html

validFilenameChars = "-_.()%s%s" % (string.ascii_letters, string.digits)

def removeDisallowedFilenameChars(filename):
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    clist = []
    for c in cleanedFilename:
        if not c in validFilenameChars:
            c = "_"
        clist.append(c)
    return ''.join(clist)

def list_to_html(input_list):
    result = html.Ul(
        [html.Li(s) for s in input_list]
    )
    return result
