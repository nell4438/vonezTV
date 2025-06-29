from flask import Flask, render_template, request, redirect, url_for
import json
import requests
import os

app = Flask(__name__)
api_key = os.environ.get('TMDB_API_KEY', "ebad75d444db2d272a470389a56d12e9")


@app.route("/view/movie/<id>")
def movie(id):
    tmdb_id = id
    
    # Get IMDB ID
    imdb_req = requests.get(
        f"http://api.themoviedb.org/3/movie/{id}/external_ids?api_key={api_key}"
    ).json()
    imdb_id = imdb_req["imdb_id"]
    
    # Get movie details
    api = requests.get(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}"
    )
    resp = api.json()
    
    # Check if vidsrc is playable
    vidsrc_url = f"https://vidjoy.pro/embed/movie/{tmdb_id}"
    vidsrc_playable = False
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        }
        vidsrc_response = requests.get(vidsrc_url, headers=headers, timeout=5)
        
        # Check if the response is valid and doesn't contain error indicators
        if vidsrc_response.status_code == 200:
            content = vidsrc_response.text.lower()
            if not any(error in content for error in ['404', 'not found', 'error', 'unavailable']):
                vidsrc_playable = True
    except Exception as e:
        print(f"Error checking vidsrc: {e}")
        vidsrc_playable = False

    # Only get torrent information if vidsrc is not playable
    info_hash = None
    file_name = None
    
    if not vidsrc_playable:
        # Get torrent information
        headers = {
            'sec-ch-ua-platform': '"Windows"',
            'Referer': '',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Brave";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
        }
        
        torrent_api_url = f"https://torrentio.strem.fun/providers=yts,eztv,rarbg,1337x,thepiratebay,kickasstorrents,torrentgalaxy,magnetdl,horriblesubs,nyaasi,tokyotosho,anidex/stream/movie/{imdb_id}.json"
        
        try:
            torrent_response = requests.get(torrent_api_url, headers=headers)
            torrent_data = torrent_response.json()
            
            if torrent_data and "streams" in torrent_data and torrent_data["streams"]:
                # Try to find 1080p stream first
                stream = None
                for s in torrent_data["streams"]:
                    if "1080p" in s.get("name", ""):
                        stream = s
                        break
                
                # If no 1080p stream found, use the first available stream
                if not stream and torrent_data["streams"]:
                    stream = torrent_data["streams"][0]
                
                if stream:
                    info_hash = stream.get("infoHash")
                    file_name = stream.get("behaviorHints", {}).get("filename")
                    
        except Exception as e:
            print(f"Error getting torrent info: {e}")

    # Process movie details
    title = resp["title"]
    movie_overview = resp["overview"]
    movie_runtime = f"{resp['runtime']} min."
    movie_rating = f"{resp['vote_average']}/10"
    movie_bg = f"https://image.tmdb.org/t/p/original/{resp['backdrop_path']}"
    poster_path = resp["poster_path"]
    date = resp["release_date"].split("-")
    rls_year = date[0]
    
    year = f"({rls_year})" if rls_year else ""
    tagline = resp["tagline"]

    return render_template(
        "movie.html",
        title=title,
        tmdb_id=tmdb_id,
        movie_overview=movie_overview,
        movie_runtime=movie_runtime,
        movie_rating=movie_rating,
        movie_bg=movie_bg,
        poster_path=poster_path,
        year=year,
        tagline=tagline,
        imdb_id=imdb_id,
        info_hash=info_hash,
        file_name=file_name,
        vidsrc_playable=vidsrc_playable
    )


@app.route("/")
def index():
    return redirect("/browse")


@app.route("/search")
def search():
    return render_template("search.html")


@app.route("/results")
def results():
    query = request.args.get("q")
    page = request.args.get("p") or 1
    if query is None:
        return render_template("search.html")
    else:
        req = requests.get(
            f"http://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}&page={page}"
        )
        resp = req.json()
        if resp == json.loads('{"errors": ["query must be provided"]}'):
            msg = "You need to provide a query!"
            code = 403
            return render_template("error.html", msg=msg, code=code)
        results_length = len(resp["results"])
        if results_length == 0:
            msg = "Sorry, Not Found!"
            code = 404
            return render_template("error.html", msg=msg, code=code)
        else:
            poster_list = []
            titles = []
            tmdb_ids = []
            number = len(resp["results"])
            for poster_path in resp["results"]:
                path = poster_path["poster_path"]
                poster_list.append(poster_path["poster_path"])
            for title in resp["results"]:
                titles.append(title["title"])
            for tmdb_id in resp["results"]:
                tmdb_ids.append(tmdb_id["id"])
            return render_template(
                "results.html",
                posters=poster_list,
                titles=titles,
                tmdb_ids=tmdb_ids,
                number=number,
                query=query,
            )


@app.route("/browse")
def browse():
    poster_list = []
    titles = []
    movie_ids = []
    page = request.args.get("p") or 1
    pop_movies = requests.get(
        f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&page={page}"
    )
    resp = pop_movies.json()
    for poster_path in resp["results"]:
        poster_list.append(poster_path["poster_path"])
    for title in resp["results"]:
        titles.append(title["title"])
    for movie_id in resp["results"]:
        movie_ids.append(movie_id["id"])
    return render_template(
        "index.html", posters=poster_list, titles=titles, movie_ids=movie_ids, page=page
    )


@app.route("/top")
def top():
    poster_list = []
    titles = []
    movie_ids = []
    page_check = request.args.get("p")
    page = request.args.get("p") or 1
    pop_movies = requests.get(
        f"https://api.themoviedb.org/3/movie/top_rated?api_key={api_key}&page={page}"
    )
    resp = pop_movies.json()
    for poster_path in resp["results"]:
        poster_list.append(poster_path["poster_path"])
    for title in resp["results"]:
        titles.append(title["title"])
    for movie_id in resp["results"]:
        movie_ids.append(movie_id["id"])
    return render_template(
        "top.html", posters=poster_list, titles=titles, movie_ids=movie_ids, page=page
    )


@app.route("/api/player")
def player():
    tmdb_id = request.args.get("id")
    if tmdb_id is None or not tmdb_id:
        return "ID Is A Required Parameter!"
    else:
        imdb_req = requests.get(
            f"http://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={api_key}"
        ).json()
        imdb_id = imdb_req["imdb_id"]
        return render_template("player.html", tmdb_id=tmdb_id, imdb_id=imdb_id)


@app.route("/search/tv")
def tv_search():
    return render_template("search_tv.html")


@app.route("/results/tv")
def tv_results():
    query = request.args.get("q")
    page = request.args.get("p") or 1
    if query is None:
        return render_template("search.html")
    else:
        req = requests.get(
            f"http://api.themoviedb.org/3/search/tv?api_key={api_key}&query={query}&page={page}"
        )
        resp = req.json()
        if resp == json.loads('{"errors": ["query must be provided"]}'):
            msg = "You need to provide a query!"
            code = 403
            return render_template("error.html", msg=msg, code=code)
        results_length = len(resp["results"])
        if results_length == 0:
            msg = "Sorry, Not Found!"
            code = 404
            return render_template("error.html", msg=msg, code=code)
        else:
            poster_list = []
            titles = []
            tmdb_ids = []
            number = len(resp["results"])
            for poster_path in resp["results"]:
                poster_list.append(poster_path["poster_path"])
            for title in resp["results"]:
                titles.append(title["name"])
            for tmdb_id in resp["results"]:
                tmdb_ids.append(tmdb_id["id"])
            return render_template(
                "results_tv.html",
                posters=poster_list,
                titles=titles,
                tmdb_ids=tmdb_ids,
                number=number,
                query=query,
            )


@app.route("/view/tv/<id>")
def tv(id):
    tmdb_id = id
    imdb_req = requests.get(
        f"http://api.themoviedb.org/3/tv/{id}/external_ids?api_key={api_key}"
    ).json()
    imdb_id = imdb_req["imdb_id"]
    api = requests.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={api_key}")
    resp = api.json()
    print(resp)
    title = resp["name"]
    tv_overview = resp["overview"]
    # tv_runtime = f"{resp['episode_run_time'][0]} min."
    tv_rating = f"{resp['vote_average']}/10"
    tv_bg = f"https://image.tmdb.org/t/p/original/{resp['backdrop_path']}"
    date = resp["first_air_date"].split("-")
    rls_year = date[0]
    seasons = resp["seasons"]
    # print(seasons)
    if rls_year == "":
        year = ""
    else:
        year = f"({rls_year})"

    return render_template(
        "tv.html",
        title=title,
        tmdb_id=tmdb_id,
        tv_overview=tv_overview,
        # tv_runtime=tv_runtime,
        tv_rating=tv_rating,
        tv_bg=tv_bg,
        year=year,
        imdb_id=imdb_id,
        seasons=seasons,
    )


@app.route("/view/tv/<id>/<s>/<e>")
def s_tv(id, s, e):
    try:
        # Get episode info
        resp = requests.get(
            f"https://api.themoviedb.org/3/tv/{id}/season/{s}/episode/{e}?api_key={api_key}"
        ).json()
        
        overview = resp["overview"]
        title = resp["name"]
        air_date = resp["air_date"].split("-")
        year = air_date[0]
        rating = round(float(resp["vote_average"]), 1)

        # Get TV show info
        tv_resp = requests.get(
            f"https://api.themoviedb.org/3/tv/{id}?api_key={api_key}"
        ).json()
        # print(tv_resp)
        seasons_array = []
        seasondicts = tv_resp["seasons"]
        
        # Get the last aired episode number
        epi_to_display = tv_resp["last_episode_to_air"]["episode_number"]
        
        for season in seasondicts:
            seasons_array.append(season["episode_count"])
        if len(seasondicts) == 1:
            current_season = int(s) - 1
        else:
            current_season = int(s) - 1

        # Use epi_to_display instead of calculating ep_count
        next_season = current_season + 1

        return render_template(
            "view_tv.html",
            id=id,
            s=s,
            e=e,
            overview=overview,
            title=title,
            year=year,
            rating=rating,
            seasons_array=seasons_array,
            current_season=current_season,
            epi_to_display=epi_to_display,  # Pass epi_to_display instead of ep_count
            next_season=next_season,
        )
    except KeyError:
        return render_template("error.html", msg="Sorry, Not Found!", code=404), 404


@app.route("/browse/tv")
def browse_tv():
    poster_list = []
    titles = []
    tv_ids = []
    page = request.args.get("p") or 1
    pop_movies = requests.get(
        f"https://api.themoviedb.org/3/tv/popular?api_key={api_key}&page={page}"
    )
    resp = pop_movies.json()
    for poster_path in resp["results"]:
        poster_list.append(poster_path["poster_path"])
    for title in resp["results"]:
        titles.append(title["name"])
    for tv_id in resp["results"]:
        tv_ids.append(tv_id["id"])
    return render_template(
        "tv_browse.html",
        posters=poster_list,
        titles=titles,
        movie_ids=tv_ids,
        page=page,
    )


@app.route("/top/tv")
def top_tv():
    poster_list = []
    titles = []
    movie_ids = []
    page_check = request.args.get("p")
    page = request.args.get("p") or 1
    pop_movies = requests.get(
        f"https://api.themoviedb.org/3/tv/top_rated?api_key={api_key}&page={page}"
    )
    resp = pop_movies.json()
    for poster_path in resp["results"]:
        poster_list.append(poster_path["poster_path"])
    for title in resp["results"]:
        titles.append(title["name"])
    for movie_id in resp["results"]:
        movie_ids.append(movie_id["id"])
    return render_template(
        "top_tv.html",
        posters=poster_list,
        titles=titles,
        movie_ids=movie_ids,
        page=page,
    )


@app.route("/api")
def api():
    return render_template("api.html")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
