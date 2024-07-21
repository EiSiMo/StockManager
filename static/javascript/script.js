document.addEventListener('DOMContentLoaded', function() {
    const items = document.querySelectorAll('.item');
    const submitButton = document.getElementById('add_button');
    const discardButton = document.getElementById('discard_button');
    const itemName = document.getElementById('item_name');
    const code = document.getElementById('product_code').textContent;

    // Disable controls if no products are to be indexed
    if (code === "Aktuell keine zu indizierenden Produkte") {
        itemName.disabled = true;
        submitButton.disabled = true;
        discardButton.disabled = true;
        itemName.style.opacity = '0.5';
        submitButton.style.opacity = '0.5';
        discardButton.style.opacity = '0.5';
    } else {
        items.forEach(item => {
            item.addEventListener('click', function() {
                items.forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                if (item.textContent !== "+ NEUER EINTRAG") {
                    itemName.disabled = true;
                    itemName.value = "";
                    itemName.style.opacity = '0.5';
                } else {
                    itemName.disabled = false;
                    itemName.style.opacity = '1.0';
                }
            });
        });
        items[0].classList.add("selected");
    }

    // Handle submit button click
    submitButton.addEventListener('click', function() {
        const selected = document.querySelector('.item.selected');
        if ((selected.textContent === "+ NEUER EINTRAG" && itemName.value) || selected.textContent !== "+ NEUER EINTRAG") {
            let selectedName = selected.textContent === "+ NEUER EINTRAG" ? "" : selected.textContent;
            const data = {
                name: itemName.value + selectedName,
                code: code
            };

            fetch('/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => console.log('Success:', data))
            .catch(error => console.error('Error:', error));

            location.reload(true);
        } else {
            alert("Bitte gib einen Produktnamen ein");
        }
    });

    // Handle discard button click
    discardButton.addEventListener('click', function() {
        location.reload(true);
    });

    // Filter items based on input
    itemName.addEventListener('input', function() {
        const filter = itemName.value.toLowerCase().trim();
        items.forEach(item => {
            if (item.textContent.toLowerCase().includes(filter) || item.textContent === "+ NEUER EINTRAG") {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
    });
});
