#!/usr/bin/python

from urllib2 import urlopen
from BeautifulSoup import BeautifulSoup as BS
from urlparse import urlparse
import os
from random import randint

# import our config
from ConfigParser import RawConfigParser as ConfigParser
import os.path
import os

# move our working directory to the current dir
here = os.path.dirname(os.path.realpath(__file__))
os.chdir(here)
config = ConfigParser()
config.read(os.path.join(here,'rip.conf'))

# settings from config
SEARCH_URL_TEMPLATE = config.get('urls','search_url_template')
CATEGORY_URL_TEMPLATE = config.get('urls','category_url_template')

RESULTS_PER_PAGE = config.getint('settings','results_per_page')
MAX_RESULTS_PER_CATEGORY = config.getint('settings','max_results_per_category')

ARCHIVE_DIR = config.get('paths','archive_dir')
OUT_DIR = config.get('paths','out_dir')


def get_soup(url):
    # get our html soup
    lines = urlopen(url).readlines()
    soup = BS(' '.join(lines))
    return soup

def get_args(url):
    # some of the urls have '?' where they should have '&'
    s = url.split('?')
    url = '%s?%s' % (s[0],'&'.join(s[1:]))

    args = dict(( x.split('=') for x in urlparse(url).query.split('&') ))
    return args

def get_torrent_urls(url):
    url_details = urlparse(url)

    # grab the front page's detail links
    # these links are relative
    detail_links = get_detail_links(url)
    torrent_urls = []

    # grab the torrent url for each of the links
    for url in detail_links:
        torrent_url = get_torrent_url_from_detail_page(url)

        # we get back a relative url, make it absolute
        torrent_url = '%s://%s%s' % (url_details.scheme,
                                     url_details.netloc,
                                     torrent_url)

        torrent_urls.append(torrent_url)

    return torrent_urls

def get_torrent_url_from_detail_page(url):

    # we can be tricky here and bypass the detail page itself
    path_pieces = [x for x in url.split('/') if x]
    dl_id = path_pieces[1]

    # give it a random # for a name if it doesn't have one
    if len(path_pieces) == 3:
        dl_name = path_pieces[2]
    else:
        dl_name = randint(111111,999999)

    dl_url = '/download.php?id=%s&name=%s' % (dl_id,dl_name)

    return dl_url

def get_detail_links(url):
    soup = get_soup(url)

    # what are we looking for?
    detail_links = []

    # find all the detailed info div's
    for detailed_info in soup.findAll('div',{'class':'div_detailed'}):
        # grab the link
        link = detailed_info.find('a').get('href')
        detail_links.append(link)

    return detail_links

def get_category_names():
    URL = 'http://www.nutorrent.com/'
    soup = get_soup(URL)

    table = soup.find('table',{'class':'cat_table'})
    cat_links = [l.get('href') for l in table.findAll('a')]
    return [[x for x in c.split('/') if x][-1] for c in cat_links]

def get_torrent_name_from_url(url):
    return get_args(url).get('name','unknown')

def get_category_count(cat_name):
    soup = get_soup(CATEGORY_URL_TEMPLATE % cat_name)

    # find a link for a later page in the category
    links = [l for l in soup.findAll('a')
                if l.get('href').startswith('/sections.php')]

    # if we didn't get any, than there is only one page worths aka < 15
    if not links:
        return RESULTS_PER_PAGE

    # the first one will do
    link = links[0]
    args = get_args(link.get('href'))
    size = int(args.get('total'))
    return min(MAX_RESULTS_PER_CATEGORY,size)

def run():

    out_paths = []
    torrent_urls = []

    # get all the categories from the website
    categories = get_category_names()

    # import our config to see which one's we're going to use
    our_categories = [n for n,a in config.items('categories')]
    categories = [c for c in categories if c.lower() in our_categories]

    for cat_name in categories:
        # find out the total # of results
        total = get_category_count(cat_name)

        print
        print 'category: %s %s' % (cat_name,total)

        # we are going to go through the pages of the category manually
        # tracking our position in the results skipping ahead one page
        # at a time using the site's search

        for i in xrange(0,total,RESULTS_PER_PAGE):
            result_url = SEARCH_URL_TEMPLATE % {'total':total,
                                                'cname':cat_name,
                                                'skip':i}

            result_torrent_urls = get_torrent_urls(result_url)

            # go through our torrents
            for torrent_url in result_torrent_urls:

                # we are going to save it using it's name
                torrent_name = get_torrent_name_from_url(torrent_url)

                # now that we know where the torrent is d/l it and drop
                # it in it's new home
                path = os.path.abspath(os.path.join(OUT_DIR,
                                          '%s.torrent' % torrent_name[:50]))

                # don't re-download it if it's in the output
                # or th archive
                archive_hash = str(hash('%s.torrent' % torrent_name))
                archive_path = os.path.abspath(os.path.join(ARCHIVE_DIR,
                                                            archive_hash))
                if os.path.exists(path) or os.path.exists(archive_path):
                    continue

                print '.',

                # keep track of what we are doing
                out_paths.append(path)
                torrent_urls.append(torrent_url)

                # download and save
                # print 'saving to: \n%s\n%s' % (path,torrent_url)
                with file(path,'wb') as fh:
                    data = urlopen(torrent_url).read()
                    #print 'file size: %s' % len(data)
                    fh.write(data)

                    # update the archive
                    file(archive_path,'w').close()


    return zip(torrent_urls,out_paths)

if __name__ == '__main__':
    print 'running'
    run()
