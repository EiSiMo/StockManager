document.addEventListener('DOMContentLoaded', function() {
    const items = document.querySelectorAll('.item');
    const submitButton = document.getElementById('add_button');
    const discardButton = document.getElementById('discard_button');
    const item_name = document.getElementById('item_name');
    const code = document.getElementById('product_code').textContent;

    if (code == "Aktuell keine zu indizierenden Produkte") {
        item_name.disabled = true;
        submitButton.disabled = true;
        discardButton.disabled = true;

        item_name.style.opacity = '0.5';
        submitButton.style.opacity = '0.5';
        discardButton.style.opacity = '0.5';
    } else {
        items.forEach(item => {
            item.addEventListener('click', function() {
                items.forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                if (item.textContent != "+ NEUER EINTRAG") {
                    item_name.disabled = true;
                    item_name.value = "";
                    item_name.style.opacity = '0.5';
                } else {
                    item_name.disabled = false;
                    item_name.style.opacity = '1.0';
                };
            });
        });
        items[0].classList.add("selected");
    }


    submitButton.addEventListener('click', function() {
        const selected = document.querySelector('.item.selected');
        console.log(selected.textContent)
        if ((selected.textContent == "+ NEUER EINTRAG" && item_name.value) || selected.textContent != "+ NEUER EINTRAG") {
            const data = {
                item_selected: selected.textContent,
                item_name: item_name.value,
                item_code: code
            };

            fetch('/new', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        } else {
            alert("Bitte gib einen Produktnamen ein");
        }
        location.reload(true);
    });

    discardButton.addEventListener('click', function() {

        const data = {
            item_code: code
        };

        fetch('/discard', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
        })
        .catch(error => {
            console.error('Error:', error);
        });

        location.reload(true);
    });

    item_name.addEventListener('input', function() {
        const filter = item_name.value.toLowerCase();
        items.forEach(item => {
            if (item.textContent.toLowerCase().includes(filter) || item.textContent == "+ NEUER EINTRAG") {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
    });
});