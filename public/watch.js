player = document.getElementById('player')
playerContainer = document.getElementById('playerContainer')
buffers = document.getElementById('buffers')
seekbar = document.getElementById('seekbar')
pfp = document.getElementById('pfp')
details = document.getElementById('details')

params = urlParams = new URLSearchParams(window.location.search)

let db

fetch(`${window.location.origin}/api/db`)
	.then((res) => res.json())
	.then((data) => {
		pfp.src = data.pfp
		db = data.videos
		entry = params.get('entry')
		player.src = db[entry].file
		details.innerHTML = `
            <div class="column">
                <img id="cover" src="${db[entry].cover}" />
                <a id="anilist" href="${db[entry].url}">
                    <svg id="aniListIcon" width="361" height="273" viewBox="0 0 361 273" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M246.921 203.272V16.602C246.921 5.90401 241.034 0 230.363 0H193.93C183.258 0 177.369 5.90401 177.369 16.602V105.253C177.369 107.75 201.365 119.342 201.992 121.794C220.274 193.404 205.964 250.714 188.633 253.394C216.97 254.799 220.088 268.458 198.981 259.125C202.21 220.916 214.809 220.991 251.03 257.719C251.34 258.036 258.457 273.001 258.9 273.001H344.445C355.117 273.001 361.003 267.101 361.003 256.401V219.877C361.003 209.179 355.117 203.275 344.445 203.275L246.921 203.272Z" fill="#02A9FF" />
                        <path d="M95.681 0.00195312L0 273.002H74.338L90.53 225.78H171.49L187.316 273.002H261.284L165.97 0.00195312H95.681ZM107.457 165.282L130.64 89.653L156.033 165.282H107.457Z" fill="#FEFEFE" />
                    </svg>
                    AniList
                </a>
            </div>
            <div class="column">
                <p class="title">${entry.slice(5).replaceAll('<', '&lt;')}</p>
                <p>${db[entry].description}</p>
            </div> 
        `
	})

marked = false

function playpause(checkfocus = false) {
	if (player.paused || player.ended) {
		player.play()
		document.getElementById('play').classList.add('hidden')
		document.getElementById('pause').classList.remove('hidden')
		seekerInterval = setInterval(progress, 500)
		playerContainer.classList.remove('showControls')
	} else {
		if (checkfocus && !focused) {
			playerContainer.classList.add('showControls')
			hideTimeout = setTimeout(() => {
				playerContainer.classList.remove('showControls')
			}, 1000)
			return
		}
		player.pause()
		document.getElementById('pause').classList.add('hidden')
		document.getElementById('play').classList.remove('hidden')
		clearInterval(seekerInterval)
		playerContainer.classList.add('showControls')
	}
}

function skip(amount) {
	player.currentTime += amount
	progress()
	playerContainer.classList.add('show-controls')
	if (typeof hideTimeout != 'undefined') {
		clearTimeout(hideTimeout)
	}
	hideTimeout = setTimeout(() => {
		playerContainer.classList.remove('showControls')
	}, 1000)
}

function fullscreen() {
	if (document.fullscreenElement) {
		document.exitFullscreen()
	} else {
		playerContainer.requestFullscreen()
	}
}

function progress() {
	percentage = (player.currentTime / player.duration).toFixed(2)
	width = Math.round(seekbar.offsetWidth * percentage)
	document.getElementById('progress').style.width = width + 'px'
	time()
	if (percentage > 0.85 && !marked) {
		marked = true
		fetch(`${window.location.origin}/api/watched`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({
				title: entry.slice(5).replaceAll('<', '&lt;'),
				episode: db[entry].episode,
			}),
		})
	}
}

function time() {
	left = Math.round(player.duration - player.currentTime)
	if (left > 3600) {
		document.getElementById('time').innerHTML = '-' + new Date(left * 1000).toISOString().slice(11, 19)
	} else {
		document.getElementById('time').innerHTML = '-' + new Date(left * 1000).toISOString().slice(14, 19)
	}
}

function buffer() {
	buffers.innerHTML = ''
	for (i = 0; i < player.buffered.length; i++) {
		start = Math.round((player.buffered.start(i) / player.duration) * 100)
		len = Math.round(((player.buffered.end(i) - player.buffered.start(i)) / player.duration) * 100)
		buffers.innerHTML += `<div class="buffer" style="width:${len}%; left:${start}%"></div>`
	}
}

async function seekStart(event) {
	updateSeek(event)
	seekbar.addEventListener('pointermove', updateSeek)
	if (typeof seekerInterval != 'undefined') {
		clearInterval(seekerInterval)
	}
}

function seekEnd() {
	seekbar.removeEventListener('pointermove', updateSeek)
	seekerInterval = setInterval(progress, 500)
}

function updateSeek(event) {
	rect = seekbar.getBoundingClientRect()
	pos = event.clientX - rect.left
	percentage = pos / rect.width
	player.currentTime = player.duration * percentage
	document.getElementById('progress').style.width = pos + 'px'
	time()
}

function logout() {
	choice = confirm('Logout?')
	if (choice) {
		location.href = '/api/logout'
	}
}

document.addEventListener('keydown', (event) => {
	switch (event.key) {
		case ' ':
		case 'k':
			event.preventDefault()
			playpause()
			break
		case 'l':
		case 'ArrowRight':
			event.preventDefault()
			skip(10)
			break
		case 'j':
		case 'ArrowLeft':
			event.preventDefault()
			skip(-10)
			break
		case 'f':
			event.preventDefault()
			fullscreen()
			break
	}
})

window.addEventListener('focus', () => {
	focusTimer = setTimeout(() => {
		focused = true
	}, 100)
})

window.addEventListener('blur', () => {
	focused = false
	clearTimeout(focusTimer)
})

window.addEventListener('fullscreenchange', () => {
	if (document.fullscreenElement) {
		document.getElementById('enterFS').classList.add('hidden')
		document.getElementById('exitFS').classList.remove('hidden')
	} else {
		document.getElementById('enterFS').classList.remove('hidden')
		document.getElementById('exitFS').classList.add('hidden')
	}
})

setInterval(buffer, 100)
