elems = {
	videos: document.getElementById('videos'),
	schedule: document.getElementById('entries'),
	pfp: document.getElementById('pfp'),
}

tick = `<svg class="tick" width="11" height="10" viewBox="0 0 11 10" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 4.5L3.73167 7.61701C4.08842 8.25915 4.9926 8.31036 5.41957 7.71261L9.5 2" stroke="black" stroke-width="3" stroke-linecap="round"/></svg> `

async function getDb() {
	fetch(`${window.location.origin}/api/db`)
		.then((res) => res.json())
		.then((data) => {
			elems.videos.innerHTML = ''
			videos = data.videos
			Object.entries(videos)
				.reverse()
				.forEach(([key, entry]) => {
					element = `
                <a class="card ${entry.status == 'ready' ? '' : 'disabled'}" href="/watch.html?entry=${key}">
                    <img class="cover" src="${entry.cover}">
                    <div class="shadow"></div>
                    <div class="content">
                        <div class="labels">
                            <p class="label">${entry.watched != null ? tick : ''}EP ${entry.episode}</p>
                            <p class="label secondary ${entry.status == 'ready' ? 'hidden' : ''}">${entry.status}</p>
                        </div>
                        <p class="title">${key.slice(5).replaceAll('<', '&lt;')}</p>
                    </div>
                </a>
            `
					elems.videos.innerHTML += element
				})
			children = elems.videos.children.length
			if (children % 2 == 1) {
				elems.videos.innerHTML += '<div id="filler"></div>'
			}
		})
}

async function getSchedule() {
	elems.schedule.innerHTML = ''
	res = await fetch(`${window.location.origin}/api/schedule`)
	list = await res.json()
	list.sort((a, b) => a.airing - b.airing).forEach((entry) => {
		title = entry.title.english || entry.title.romaji
		time = new Date(entry.airing * 1000)
		time = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
		elems.schedule.innerHTML += `
            <div class="scheduleEntry${entry.airing * 1000 < Date.now() ? ' past' : ''}">
                <div class="row">
                    <p class="time">${time}</p>
                    <p class="episode">EP ${entry.episode}</p>
                </div>    
                <p class="title">${title.replaceAll('<', '&lt;')}</p>
            </div>
        `
	})
}

function logout() {
	choice = confirm('Logout?')
	if (choice) {
		location.href = '/api/logout'
	}
}

fetch(`${window.location.origin}/api/db`)
	.then((res) => res.json())
	.then((data) => {
		elems.pfp.src = data.pfp
	})

getDb()
getSchedule()
setInterval(getDb, 10000)
