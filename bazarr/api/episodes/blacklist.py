# coding=utf-8

import datetime
import pretty

from flask import request, jsonify
from flask_restful import Resource

from database import TableEpisodes, TableShows, TableBlacklist
from ..utils import authenticate, postprocessEpisode
from utils import blacklist_log, delete_subtitles, blacklist_delete_all, blacklist_delete
from get_subtitle import episode_download_subtitles
from event_handler import event_stream


# GET: get blacklist
# POST: add blacklist
# DELETE: remove blacklist
class EpisodesBlacklist(Resource):
    @authenticate
    def get(self):
        start = request.args.get('start') or 0
        length = request.args.get('length') or -1

        data = TableBlacklist.select(TableShows.title.alias('seriesTitle'),
                                     TableEpisodes.season.concat('x').concat(TableEpisodes.episode).alias('episode_number'),
                                     TableEpisodes.title.alias('episodeTitle'),
                                     TableEpisodes.seriesId,
                                     TableBlacklist.provider,
                                     TableBlacklist.subs_id,
                                     TableBlacklist.language,
                                     TableBlacklist.timestamp)\
            .join(TableEpisodes)\
            .join(TableShows)\
            .order_by(TableBlacklist.timestamp.desc())\
            .limit(length)\
            .offset(start)\
            .dicts()
        data = list(data)

        for item in data:
            # Make timestamp pretty
            item["parsed_timestamp"] = datetime.datetime.fromtimestamp(int(item['timestamp'])).strftime('%x %X')
            item.update({'timestamp': pretty.date(datetime.datetime.fromtimestamp(item['timestamp']))})

            postprocessEpisode(item)

        return jsonify(data=data)

    @authenticate
    def post(self):
        series_id = int(request.args.get('seriesid'))
        episode_id = int(request.args.get('episodeid'))
        provider = request.form.get('provider')
        subs_id = request.form.get('subs_id')
        language = request.form.get('language')

        episodeInfo = TableEpisodes.select(TableEpisodes.path)\
            .where(TableEpisodes.episodeId == episode_id)\
            .dicts()\
            .get()

        media_path = episodeInfo['path']
        subtitles_path = request.form.get('subtitles_path')

        blacklist_log(series_id=series_id,
                      episode_id=episode_id,
                      provider=provider,
                      subs_id=subs_id,
                      language=language)
        delete_subtitles(media_type='series',
                         language=language,
                         forced=False,
                         hi=False,
                         media_path=media_path,
                         subtitles_path=subtitles_path,
                         series_id=series_id,
                         episode_id=episode_id)
        episode_download_subtitles(episode_id)
        event_stream(type='episode-history')
        return '', 200

    @authenticate
    def delete(self):
        if request.args.get("all") == "true":
            blacklist_delete_all()
        else:
            provider = request.form.get('provider')
            subs_id = request.form.get('subs_id')
            blacklist_delete(provider=provider, subs_id=subs_id)
        return '', 204
