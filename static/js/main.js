document.addEventListener('DOMContentLoaded', () => {

    const navbar = document.getElementById('navbar');

    // Handle Navbar Background on Scroll
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Horizontal Scrolling for Movie Rows with Mouse Wheel
    const rows = document.querySelectorAll('.row-posters');
    rows.forEach(row => {
        row.addEventListener('wheel', (e) => {
            // Check if scrolling over the row
            e.preventDefault();
            
            // Adjust scroll based on deltaY (up/down mouse wheel) -> translating to horizontal scroll
            row.scrollBy({
                left: e.deltaY < 0 ? -150 : 150,
                behavior: 'smooth'
            });
        });
    });

});
