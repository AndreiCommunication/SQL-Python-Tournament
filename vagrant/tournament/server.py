#
# DB Forum - a buggy web forum server backed by a good database
#

# The forumdb module is where the database interface code goes.
import tournament

# Other modules used to run a web server.
import cgi
from wsgiref.simple_server import make_server
from wsgiref import util

# HTML template for the forum page
HTML_WRAP = '''\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Swiss Tournament</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.0.0-alpha/css/bootstrap.css">
  <style>
    .flexbox {
        display: flex;
    }
    .player-listing {
      display: flex;
      font-size: 1.2rem;
    }
    .player-listing + .player-listing {
        border-top: 1px solid #999;
        }
    .player-listing__name {
      width: 15em;
    }
    .player-listing__wins {
      width: 6em;
    }
    .player-listing__matches {
      width: 6em;
    }
    .player-listing__delete {
      margin-left: 0.75em;
    }
    .swiss-pairings {
        display: flex;
    }
    .match {
      display: flex;
      font-size: 1.2rem;
      width: 14em;
    }
    .match__player {
      width: 6em;
    }
    .match__player__button {
      width: 100%%;
    }
    .hidden {
      display: none;
    }
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.2/jquery.min.js"></script>
</head>
<body>
  <div class="container">
    <div class="row" style="height: 5vh"></div>
    <div class="row" style="margin-bottom: 1em">
      <div class="col-xs-3">
        <button class="btn btn-default" id="add-player">Add Player</button>
      </div>
      <div class="col-xs-3">
        <form method="post" action="/ShowPlayers">
          <button class="btn btn-default" type="submit">Show Players</button>
        </form>
      </div>
      <div class="col-xs-3">
        <form method="post" action="/SwissPairings">
          <button class="btn btn-info" type="submit">Swiss Pairings</button>
        </form>
      </div>
      <div class="col-xs-3">
        <form method="post" action="/DeletePlayers">
          <button class="btn btn-danger" type="submit">Delete All</button>
        </form>
      </div>
    </div>
    <div class="row">
      <div class="col-xs-12">
        <form class="hidden" id="new-player-form" method="post" action="/AddPlayer">
          <input name="new-player"  type="text">
          <button class="btn btn-primary" type="submit">Add</button>
        </form>
      </div>
    </div>
    <div class="row">
      <div class="col-md-12">
        %s
      </div>
    </div>
  </div>
  <script>
    var $newPlayerForm = $('#new-player-form');
    $('#add-player').on('click', function() {
      $newPlayerForm.toggleClass('hidden');
    });
  </script>
</body>
</html>

'''

# Here we track the number of matches still to be played in the current
# round of the swiss pairings tournament. This ensures that all rounds of a
# single round are played before new pairings are made for the second round
matchesToPlay = 0
# Matches in the current round of the tournament being played
currentMatches = []
# All previous rounds in the current tournament being played.
previousRounds = []
# Rounds left to play in the current tournament before a winner is decided
roundsLeft = 0
# If tournament has not begun, we need to run init code
tournamentBegan = False
# If tournament is not over we continue to prompt for match results
tournamentOver = False
# If the tournament is over, store the round info for review.
lastTournamentResult = ''


## Delete all information regarding the current tournament to make room for a
## next tournament.
def clearTournament():
    global matchesToPlay, currentMatches, previousRounds
    matchesToPlay = 0
    currentMatches = []
    previousRounds = []
    tournament.deleteMatches()

## Clean matches not connected to a tournament
def cleanUp():
    '''
    Clear all matches stored in the database if there are no matches stored in
    the python code. This means that the tournament was closed before it was
    stored and the matches cannot be recorded.
    '''
    standings = tournament.playerStandings()
    # There are some players registered
    if standings:
        # There are matches currently stored in the database but not in the code
        if standings[0][3] and not (previousRounds or lastTournamentResult):
            clearTournament()

## Request handler for main page
def Main(env, resp):
    '''
    This the main page.
    '''
    cleanUp()
    headers = [('Content-type', 'text/html')]
    resp('200 OK', headers)
    return HTML_WRAP % ''

## Request handler for posting
def AddPlayer(env, resp):
    '''Post handles a submission of the forum's form.

    The message the user posted is saved in the database, then it sends a 302
    Redirect back to the main page so the user can see their new post.
    '''
    cleanUp()
    # Get post content
    input = env['wsgi.input']
    length = int(env.get('CONTENT_LENGTH', 0))

    # If length is zero, post is empty - don't save it.
    if length > 0:
        postdata = input.read(length)
        fields = cgi.parse_qs(postdata)
        try:
            player = fields['new-player'][0]
        except KeyError:
            print 'No input string for new player.'
            player = ''
        # If the post is just whitespace, don't save it.
        player = player.strip()
        if len(player) > 9:
            player = player[:9]
        if player:
            # Save it in the database
            clearTournament()
            tournament.registerPlayer(player)

    # 302 redirect back to the player standings
    headers = [('Location', '/ShowPlayers'),
               ('Content-type', 'text/plain')]
    resp('302 REDIRECT', headers)
    return ['Redirecting']

## HTML template for an individual player
PLAYER = '''\
    <li class="player-listing">
        <div class="player-listing__name">
            Name: <b>%(name)s</b>
        </div>
        <div class="player-listing__wins">
            Wins: <b>%(wins)s</b>
        </div>
        <div class="player-listing__matches">
            Matches: <b>%(matches)s</b>
        </div>
        <div>
            Tourny Wins: <b>%(tournyWins)s</b>
        </div>
        <div class="player-listing__delete">
            <form method="post" action="/DeleteOnePlayer">
                <input type="hidden" name="playerid" value="%(playerid)s">
                <button class="btn btn-danger" type="submit">X</button>
            </form>
        </div>

    </li>
'''

## Request handler for viewing all registered players
def ShowPlayers(env, resp):
    '''
    GETs the current list of registered players.
    '''
    cleanUp()
    # Get post content
    # get posts from database
    players = tournament.playerStandings()
    playerList = ''
    for player in players:
        playerList += PLAYER % {'name': player[1],
                                'wins': player[2],
                                'matches': player[3],
                                'playerid': player[0],
                                'tournyWins': player[4] or 0}
    formattedList = '<ul>%s</ul>' % playerList

    headers = [('Content-type', 'text/html')]
    resp('200 OK', headers)
    return HTML_WRAP % formattedList

## Removes all players from database
def DeletePlayers(env, resp):
    '''
    **DANGER**
    DELETES all the players and matches from the database.
    '''
    tournament.deleteTournaments()
    tournament.deleteMatches()
    tournament.deletePlayers()
    clearTournament()
    # 302 redirect back to the main page
    headers = [('Location', '/ShowPlayers'),
               ('Content-type', 'text/plain')]
    resp('302 REDIRECT', headers)
    return ['Redirecting']

## Remove one player from database
def DeleteOnePlayer(env, resp):
    '''
    DELETE one player from the database. Set all matches with this player in
    them to show a NULL id for this player now. Delete all matches that now
    have two null players.
    '''
    # Get post content
    input = env['wsgi.input']
    length = int(env.get('CONTENT_LENGTH', 0))


    # If length is zero, post is empty - don't save it.
    if length > 0:
        postdata = input.read(length)
        fields = cgi.parse_qs(postdata)
        try:
            playerid = fields['playerid'][0]
        except KeyError:
            print 'There is no player id present.'
            playerid = ''
        # If the player id is just white space, don't perform the post request
        playerid = playerid.strip()
        if playerid:
            # Delete the player from the database
            tournament.deletePlayer(playerid)
            clearTournament()
        else:
            print 'No playerid'
            print playerid
    else:
        print 'Length <= 0 unfortunately.'

    # 302 redirect back to the player standings
    headers = [('Location', '/ShowPlayers'),
               ('Content-type', 'text/plain')]
    resp('302 REDIRECT', headers)
    return ['Redirecting']

## HTML template for a match
PENDINGMATCH = '''\
    <li class="match">
        <div class="match__player">
            <form method="post" action="/ReportMatch">
                <input type="hidden" name="winnerid" value="%(first_player_id)s">
                <input type="hidden" name="matchindex" value="%(match_index)s">
                <button class="btn btn-info match__player__button" type="submit">%(first_player)s</button>
            </form>
        </div>
        <div class="match__vs">
            <b>v.</b>
        </div>
        <div class="match__player">
            <form method="post" action="/ReportMatch">
                <input type="hidden" name="winnerid" value="%(second_player_id)s">
                <input type="hidden" name="matchindex" value="%(match_index)s">
                <button class="btn btn-info match__player__button" type="submit">%(second_player)s</button>
            </form>
        </div>
    </li>
'''

## HTML template for a played match
PLAYEDMATCH = '''\
    <li class="match">
        <div class="match__player">
            <button class="btn btn-%(first_player_status)s match__player__button" type="submit">%(first_player)s</button>
        </div>
        <div class="match__vs">
            <b>v.</b>
        </div>
        <div class="match__player">
            <button class="btn btn-%(second_player_status)s match__player__button" type="submit">%(second_player)s</button>
        </div>
    </li>
'''

TOURNAMENTROUND = '<ul class="swiss-pairings">%s</ul>'

## Import previous rounds into swiss tournament tree
def loadPreviousRounds(formattedList):
    global previousRounds
    for round in previousRounds:
        matchList = ''
        for match in round:
            if match['winner'] == match['firstPlayerId']:
                firstPlayerStatus, secondPlayerStatus = 'success', 'default'
            else:
                secondPlayerStatus, firstPlayerStatus = 'success', 'default'
            matchList += PLAYEDMATCH % {'first_player': match['firstPlayerName'],
                                        'first_player_status': firstPlayerStatus,
                                        'second_player': match['secondPlayerName'],
                                        'second_player_status': secondPlayerStatus}
        formattedList += TOURNAMENTROUND % matchList
    return formattedList

def addPendingMatch(matchList, match):
    matchList += PENDINGMATCH % {'first_player_id': match['firstPlayerId'],
                                'first_player': match['firstPlayerName'],
                                'second_player_id': match['secondPlayerId'],
                                'second_player': match['secondPlayerName'],
                                'match_index': match['index']}
    return matchList

def addCompletedMatch(matchList, match):
    if match['winner'] == match['firstPlayerId']:
        firstPlayerStatus, secondPlayerStatus = 'success', 'default'
    else:
        secondPlayerStatus, firstPlayerStatus = 'success', 'default'
    matchList += PLAYEDMATCH % {'first_player': match['firstPlayerName'],
                                'first_player_status': firstPlayerStatus,
                                'second_player': match['secondPlayerName'],
                                'second_player_status': secondPlayerStatus}
    return matchList

def blankMatch(pairing, i):
    return {
        'firstPlayerId': pairing[0],
        'firstPlayerName': pairing[1],
        'secondPlayerId': pairing[2],
        'secondPlayerName': pairing[3],
        'winner': None,
        'alreadyPlayed': False,
        'index': i
    }

## Push completed rounds to the database and clear currentMatches
def prepareForNextRound():
    global previousRounds, currentMatches
    for match in currentMatches:
        a, b, w = int(match['firstPlayerId']), int(match['secondPlayerId']), int(match['winner'])
        winner = a if a == w else b
        loser = b if a == w else a
        tournament.reportMatch(winner, loser)
    previousRounds.append(currentMatches)
    currentMatches = []

def determineRoundsNeeded(pairs):
    n = 0
    while pairs > 2**n:
        n += 1
    return n

TOURNAMENTCONCLUSION = '''\
<h2> The winner is %s!</h2>
<div class="flexbox">
    <form method="post" action="/ReportTournament">
        <input type="hidden" name="storeTournament" value="store">
        <button class="btn btn-primary" type="submit">Store Tournament</button>
    </form>
    <form method="post" action="/ReportTournament">
        <input type="hidden" name="storeTournament" value="discard">
        <button class="btn btn-danger" type="submit">Discard Tournament</button>
    </form>
</div>
'''

## View the tournament mode
def SwissPairings(env, resp):
    '''
    Display Swiss pairings for current player set. Works only for 8 people
    currently.
    '''
    cleanUp()
    matchList = ''
    formattedList = ''
    global matchesToPlay, currentMatches, previousRounds, roundsLeft
    global tournamentBegan, tournamentOver, lastTournamentResult
    if not tournamentBegan:
        tournamentBegan = True
        pairs = len(tournament.swissPairings())
        roundsLeft = determineRoundsNeeded(pairs)
    if not tournamentOver:
        if roundsLeft and matchesToPlay == 0: # new round
            if currentMatches: # We already have a round saved
                prepareForNextRound() # Clear matches and insert into database
                roundsLeft -= 1
            i = 0 # index for the matches for the current round
            pairings = tournament.swissPairings()
            matchesToPlay = len(pairings)
            for pairing in pairings:
                currentMatches.append(blankMatch(pairing, i))
                i += 1
            formattedList = loadPreviousRounds(formattedList)
            for match in currentMatches:
                matchList = addPendingMatch(matchList, match)
        elif matchesToPlay > 0:
            formattedList = loadPreviousRounds(formattedList)
            for match in currentMatches:
                if match['alreadyPlayed']:
                    matchList = addCompletedMatch(matchList, match)
                else:
                    matchList = addPendingMatch(matchList, match)
        else:
            tournamentOver = True
            prepareForNextRound()
            lastTournamentResult = loadPreviousRounds('')
            previousRounds = []
            winner = tournament.playerStandings()[0][1]
            lastTournamentResult += TOURNAMENTCONCLUSION % (winner)

    formattedList += TOURNAMENTROUND % matchList

    if tournamentOver:
        formattedList = lastTournamentResult

    headers = [('Content-type', 'text/html')]
    resp('200 OK', headers)
    return HTML_WRAP % formattedList

## Report a winner and loser and store it in the global currentMatches
def ReportMatch(env, resp):
    '''
    Report a match and store it in the global currentMatches
    '''
    # Get post content
    input = env['wsgi.input']
    length = int(env.get('CONTENT_LENGTH', 0))
    postdata = input.read(length)
    fields = cgi.parse_qs(postdata)
    global currentMatches, matchesToPlay

    matchesToPlay -= 1

    winnerid = int(fields['winnerid'][0])
    index = int(fields['matchindex'][0])

    currentMatches[index]['winner'] = winnerid
    currentMatches[index]['alreadyPlayed'] = True

    # 302 redirect back to the swiss pairings
    headers = [('Location', '/SwissPairings'),
               ('Content-type', 'text/plain')]
    resp('302 REDIRECT', headers)
    return ['Redirecting']

## Report the tournament that had just played out
def ReportTournament(env, resp):
    '''
    Report a tournament and clear matches for a next tournament.
    '''
    # Get post content
    input = env['wsgi.input']
    length = int(env.get('CONTENT_LENGTH', 0))
    postdata = input.read(length)
    fields = cgi.parse_qs(postdata)
    choice = fields['storeTournament'][0]

    global tournamentBegan, tournamentOver, lastTournamentResult
    tournamentOver = False
    tournamentBegan = False
    lastTournamentResult = ''

    # if the user chose to store the tournament we report it
    if choice == 'store':
        tournament.reportTournament()

    # 302 redirect back to the swiss pairings
    headers = [('Location', '/ShowPlayers'),
               ('Content-type', 'text/plain')]
    resp('302 REDIRECT', headers)
    return ['Redirecting']

## Dispatch table - maps URL prefixes to request handlers
DISPATCH = {'': Main,
            'AddPlayer': AddPlayer,
            'ShowPlayers': ShowPlayers,
            'DeletePlayers': DeletePlayers,
            'DeleteOnePlayer': DeleteOnePlayer,
            'SwissPairings': SwissPairings,
            'ReportMatch': ReportMatch,
            'ReportTournament': ReportTournament
	    }

## Dispatcher forwards requests according to the DISPATCH table.
def Dispatcher(env, resp):
    '''Send requests to handlers based on the first path component.'''
    page = util.shift_path_info(env)
    if page in DISPATCH:
        return DISPATCH[page](env, resp)
    else:
        status = '404 Not Found'
        headers = [('Content-type', 'text/plain')]
        resp(status, headers)
        return ['Not Found: ' + page]


# Run this bad server only on localhost!
httpd = make_server('', 8000, Dispatcher)
print "Serving HTTP on port 8000..."
httpd.serve_forever()
