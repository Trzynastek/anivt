player = document.getElementById('player')
playerContainer = document.getElementById('playerContainer')
buffers = document.getElementById('buffers')
seekbar = document.getElementById('seekbar')
pfp = document.getElementById('pfp')

params = urlParams = new URLSearchParams(window.location.search)

fetch(`${window.location.origin}/api/db`)
	.then((res) => res.json())
	.then((data) => {
		pfp.src = data.pfp
	})

player.src = params.get('file')
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
				title: params.get('title'),
				episode: params.get('episode'),
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
