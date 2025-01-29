import os
from flask import Flask, send_from_directory, jsonify, flash, render_template, request, redirect, url_for, session
import mysql.connector
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest


logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'admin_secret_key'  # Required for session management



# Configure MySQL connection
def get_db_connection():
    db = mysql.connector.connect(
        host="localhost",
        user="admin",      # Replace with your MySQL username
        password="1234",   # Replace with your MySQL password
        database="profiling_system"   # Replace with your database name
    )

    return db


# ADMIN
@app.route('/admin/pages/samples/register.html', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate input fields
        if not all([first_name, last_name, username, email, password, confirm_password]):
            flash("All fields are required.", "danger")
            return redirect(url_for('admin_register'))

        # Validate password match
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('admin_register'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        try:
            db = get_db_connection()
            cursor = db.cursor()

            # Step 1: Check if username or email already exists
            cursor.execute(
                "SELECT id FROM admin_users WHERE username = %s OR email = %s",
                (username, email),
            )
            if cursor.fetchone():
                flash("Username or email already exists.", "danger")
                return redirect(url_for('admin_register'))

            # Step 2: Insert the admin user into admin_users table
            cursor.execute(
                """
                INSERT INTO admin_users (username, email, password, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, email, hashed_password, first_name, last_name),
            )
            db.commit()
            flash("Admin registered successfully!", "success")

        except Exception as e:
            db.rollback()
            logging.error(f"Error in admin_register: {e}")
            flash("An unexpected error occurred. Please try again later.", "danger")
        finally:
            cursor.close()
            db.close()

        return redirect(url_for('admin_register'))

    return render_template('/admin/pages/samples/register.html')

# Admin Account Settngs Route
@app.route('/admin/pages/account.html', methods=['GET', 'POST'])
def admin_account():
    if not session.get('logged_in'):
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for('admin_login'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    username = session.get('username')  # Username stored during login

    if request.method == 'POST':
        # Handle form submission
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')  # Note: Hash the password in real-world applications

        try:
            # Update admin user details
            cursor.execute(
                """UPDATE admin_users
                   SET first_name = %s, last_name = %s, email = %s, password = %s
                   WHERE username = %s""",
                (first_name, last_name, email, password, username)
            )
            db.commit()
            flash("Account details updated successfully.", "success")
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('admin_account'))

    # Fetch user details for GET request
    try:
        cursor.execute(
            "SELECT username, email, password, first_name, last_name FROM admin_users WHERE username = %s",
            (username,)
        )
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

    finally:
        cursor.close()
        db.close()

    return render_template(
        '/admin/pages/account.html',
        username=user_details['username'],
        email=user_details['email'],
        password=user_details['password'],  # In a real app, avoid passing plaintext passwords
        first_name=user_details['first_name'],
        last_name=user_details['last_name']
    )

# Admin Login Route
@app.route('/admin/pages/samples/login.html', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Query the database for the admin user
        db = get_db_connection()  # Get DB connection
        cursor = db.cursor()
        cursor.execute("SELECT id, username, email, password FROM admin_users WHERE email=%s", (email,))
        user = cursor.fetchone()

        # Debugging: Print user data
        print("User Data:", user)

        # Check if the user exists and the password is correct
        if user and check_password_hash(user[3], password):  # Assuming column 3 is password
            session['logged_in'] = True
            session['user_id'] = user[0]  # Store the user's ID in the session
            session['username'] = user[1]  # Assuming column 1 is username
            flash("Login successful!", "success")
            return redirect(url_for('admin_index'))  # Redirect to admin dashboard
        else:
            flash("Invalid email or password.", "danger")

        cursor.close()  # Close the cursor
        db.close()  # Close the database connection

    return render_template('/admin/pages/samples/login.html')

# Admin Dashboard Route
from datetime import datetime
@app.route('/admin/index', methods=['GET'])
def admin_index():
    if not session.get('logged_in'):
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for('admin_login'))

    # Database connection
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Fetch admin user details
        username = session.get('username')  # Username stored during login
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()  # Fetch user details

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

        # Get the 'year' query parameter, if available
        selected_year = request.args.get('year', default=None, type=int)

        # Define base query for age classification
        age_query = """
            SELECT 
                birthday,
                CASE 
                    WHEN TIMESTAMPDIFF(YEAR, birthday, CURDATE()) BETWEEN 15 AND 17 THEN 'Child Youth'
                    WHEN TIMESTAMPDIFF(YEAR, birthday, CURDATE()) BETWEEN 18 AND 24 THEN 'Core Youth'
                    WHEN TIMESTAMPDIFF(YEAR, birthday, CURDATE()) BETWEEN 25 AND 30 THEN 'Young Adult'
                    WHEN TIMESTAMPDIFF(YEAR, birthday, CURDATE()) >= 31 THEN 'Adult'
                    ELSE NULL
                END AS age_group,
                DATE(created_at) = CURDATE() AS is_new_today
            FROM kk_profiles
            WHERE 1=1
        """

        # Modify query to filter by account creation year if 'year' is provided
        if selected_year:
            age_query += " AND YEAR(created_at) = %s"
            cursor.execute(age_query, (selected_year,))
        else:
            cursor.execute(age_query)

        age_data = cursor.fetchall()  # Fetch all the data

        # Count totals for all groups
        total_members = 0
        child_youth = 0
        core_youth = 0
        young_adult = 0
        adult = 0
        new_child_youth = 0
        new_core_youth = 0
        new_young_adult = 0
        new_adult = 0

        for row in age_data:
            if row['age_group']:
                total_members += 1
                if row['age_group'] == 'Child Youth':
                    child_youth += 1
                    if row['is_new_today']:
                        new_child_youth += 1
                elif row['age_group'] == 'Core Youth':
                    core_youth += 1
                    if row['is_new_today']:
                        new_core_youth += 1
                elif row['age_group'] == 'Young Adult':
                    young_adult += 1
                    if row['is_new_today']:
                        new_young_adult += 1
                elif row['age_group'] == 'Adult':
                    adult += 1
                    if row['is_new_today']:
                        new_adult += 1

        # Fetch total new members registered today
        new_members_query = """
        SELECT COUNT(*) AS new_members_today
        FROM kk_profiles
        WHERE DATE(created_at) = CURDATE();
        """
        cursor.execute(new_members_query)
        new_members_result = cursor.fetchone()
        new_members_today = new_members_result['new_members_today'] if new_members_result else 0

        # Prepare dashboard data
        dashboard_data = {
            'total_kk_members': total_members,
            'child_youth': child_youth,
            'core_youth': core_youth,
            'young_adult': young_adult,
            'adult': adult,
            'new_members_today': new_members_today,
            'new_child_youth': new_child_youth,
            'new_core_youth': new_core_youth,
            'new_young_adult': new_young_adult,
            'new_adult': new_adult
        }

        # Query for gender distribution for all age groups
        gender_query = """
        SELECT 
            gender, COUNT(*) AS gender_count
        FROM kk_profiles
        WHERE 1=1
        """
        # Apply year filter for gender distribution
        if selected_year:
            gender_query += " AND YEAR(created_at) = %s GROUP BY gender"
            cursor.execute(gender_query, (selected_year,))
        else:
            gender_query += " GROUP BY gender"
            cursor.execute(gender_query)
        gender_data = cursor.fetchall()

        # Query for voter status for all age groups
        voter_status_query = """
        SELECT 
            voter_status, COUNT(*) AS voter_count
        FROM kk_profiles
        WHERE 1=1
        """
        # Apply year filter for voter status distribution
        if selected_year:
            voter_status_query += " AND YEAR(created_at) = %s GROUP BY voter_status"
            cursor.execute(voter_status_query, (selected_year,))
        else:
            voter_status_query += " GROUP BY voter_status"
            cursor.execute(voter_status_query)
        voter_data = cursor.fetchall()

        # Query for youth classification for all age groups
        youth_classification_query = """
        SELECT 
            youth_classification, COUNT(*) AS classification_count
        FROM kk_profiles
        WHERE 1=1
        """
        # Apply year filter for youth classification distribution
        if selected_year:
            youth_classification_query += " AND YEAR(created_at) = %s GROUP BY youth_classification"
            cursor.execute(youth_classification_query, (selected_year,))
        else:
            youth_classification_query += " GROUP BY youth_classification"
            cursor.execute(youth_classification_query)
        classification_data = cursor.fetchall()

    finally:
        cursor.close()
        db.close()

    # Prepare data for the template
    gender_distribution = {gender['gender']: gender['gender_count'] for gender in gender_data}
    voter_distribution = {voter['voter_status']: voter['voter_count'] for voter in voter_data}
    classification_distribution = {classification['youth_classification']: classification['classification_count'] for classification in classification_data}

    # Pass data to the template
    return render_template(
        'admin/index.html',
        first_name=user_details['first_name'],
        last_name=user_details['last_name'],
        dashboard_data=dashboard_data,
        gender_data=gender_distribution,
        voter_data=voter_distribution,
        classification_data=classification_distribution,
        selected_year=selected_year
    )

@app.route('/admin/filter_data', methods=['GET'])
def filter_data():
    filter_type = request.args.get('filter_type', default='yearly', type=str)

    # Database connection
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        query = ""
        if filter_type == "daily":
            # Daily data: Group by day
            query = """
                SELECT 
                    DATE(created_at) AS date, COUNT(*) AS submissions 
                FROM kk_profiles
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at);
            """
        elif filter_type == "monthly":
            # Monthly data: Group by month
            query = """
                SELECT 
                    DATE_FORMAT(created_at, '%Y-%m') AS date, COUNT(*) AS submissions 
                FROM kk_profiles
                GROUP BY DATE_FORMAT(created_at, '%Y-%m')
                ORDER BY DATE_FORMAT(created_at, '%Y-%m');
            """
        elif filter_type == "yearly":
            # Yearly data: Group by year
            query = """
                SELECT 
                    YEAR(created_at) AS date, COUNT(*) AS submissions 
                FROM kk_profiles
                GROUP BY YEAR(created_at)
                ORDER BY YEAR(created_at);
            """

        cursor.execute(query)
        data = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    # Return data in JSON format
    return jsonify(data)


# Admin SK Profiles Route
@app.route('/admin/pages/sk-list')
def sk_profiles():
    if not session.get('logged_in'):
        flash("Please log in to access the SK Officials page.", "danger")
        return redirect(url_for('admin_login'))

    # Get a connection to the database
    db = get_db_connection()  # Ensure this function provides a valid DB connection
    cursor = db.cursor(dictionary=True)

    try:
        # Fetch admin user details
        username = session.get('username')  # Username stored during login
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))
        if request.method == 'POST':
            # Get the year from the form
            year_term = request.form.get('year_term')
            profile_id = request.form.get('profile_id')  # Assuming you have a way to get the profile_id

            # Update the kk_positions table with the year_term
            cursor.execute("UPDATE kk_positions SET year_term = %s WHERE profile_id = %s", (year_term, profile_id))
            db.commit()
            flash("Year term updated successfully.", "success")

        # SQL query to join profiles and positions, excluding the profile ID
        query = """
        SELECT 
            kk_positions.id AS position_id,
            kk_positions.position AS position_name,
            kk_profiles.first_name,
            kk_profiles.middle_name,
            kk_profiles.last_name,
            kk_profiles.suffix,
            kk_profiles.gender,
            kk_profiles.email,
            kk_profiles.phone,
            kk_profiles.purok,
            kk_profiles.barangay

        FROM kk_profiles
        LEFT JOIN kk_positions ON kk_profiles.id_kkprofiles = kk_positions.profile_id;
        """

        # Execute the query
        cursor.execute(query)
        users = cursor.fetchall()  # Fetch all rows

    # Close the cursor and database connection
    finally:
        cursor.close()
        db.close()

    # Render the template and pass the users data
    return render_template('admin/pages/sk-list.html',
        users=users,
        first_name=user_details['first_name'],
        last_name=user_details['last_name']
        )

# Route to assign a new position
@app.route('/assign_position', methods=['POST'])
def assign_position():
    db = get_db_connection()
    cursor = db.cursor()

    position = request.form.get('position')
    name = request.form.get('name')
    year_term = request.form.get('year_term')  # Retrieve year_term from the request data

    try:
        # Match full name in the database
        cursor.execute(
            "SELECT id_kkprofiles, email, purok FROM kk_profiles WHERE CONCAT(first_name, ' ', last_name) = %s LIMIT 1",
            (name,)
        )
        profile = cursor.fetchone()

        if profile:
            profile_id, email, purok = profile

            # Insert the position into the kk_positions table
            query = "INSERT INTO kk_positions (year_term, profile_id, position) VALUES (%s, %s, %s)"
            cursor.execute(query, (year_term, profile_id, position))
            db.commit()

            # Return the new row data to the frontend
            return jsonify({
                
                "position_id": cursor.lastrowid,  # Get the ID of the newly inserted position
                "year_term": year_term,
                "position": position,
                "name": name,
                "email": email or 'N/A',
                "purok": purok or 'N/A'
            })
        else:
            return jsonify({"error": "Name not found in profiles"}), 404

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    finally:
        # Ensure the cursor and connection are closed
        cursor.close()
        db.close()
# Route to fetch all assigned positions (for the table)
@app.route('/get_positions', methods=['GET'])
def get_positions():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Get query parameters
        year_term = request.args.get('year_term', default=None)
        name = request.args.get('name', default=None)
        position = request.args.get('position', default=None)  # New filter for position

        # Base SQL query
        query = """
        SELECT
            p.id as position_id,
            p.year_term,
            p.position, 
            CONCAT(k.first_name, ' ', k.last_name) AS name, 
            k.suffix,
            k.gender,
            k.email, 
            k.phone,
            k.purok
        FROM kk_positions p
        JOIN kk_profiles k ON p.profile_id = k.id_kkprofiles
        """
        
        # Conditions for filtering
        conditions = []
        params = []

        if year_term:
            conditions.append("p.year_term = %s")
            params.append(year_term)
        
        if name:
            conditions.append("(k.first_name LIKE %s OR k.last_name LIKE %s)")
            params.append(f"%{name}%")
            params.append(f"%{name}%")

        if position:
            conditions.append("p.position = %s")  # Add position filter condition
            params.append(position)

        # Add conditions to query if there are any
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Execute the query with parameters
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        return jsonify(rows)  # Return data to frontend

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    finally:
        cursor.close()
        db.close()

# Route to handle name suggestions for autocomplete
@app.route('/get_names', methods=['GET'])
def get_names():
    query = request.args.get('query', '')  # Get the query parameter
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Fetch matching names from `kk_profiles`
        cursor.execute(
            "SELECT id_kkprofiles, first_name, last_name FROM kk_profiles WHERE first_name LIKE %s OR last_name LIKE %s LIMIT 10",
            (f"%{query}%", f"%{query}%")
        )
        results = cursor.fetchall()

        return jsonify(results)  # Return matching names as JSON

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    finally:
        cursor.close()
        db.close()

# DELETE route to handle profile deletion
@app.route('/delete_skposition/<int:id>', methods=['DELETE'])
def delete_skposition(id):
    try:
        # Debugging the incoming request
        print(f"Received position ID to delete: {id}")  # Print the ID of the position to delete

        if not id:
            return jsonify({"status": "error", "message": "Position ID is required"}), 400

        # Connect to the database
        db = get_db_connection()
        cursor = db.cursor()

        # Delete the record from the `kk_positions` table using the `id` of the position
        query = "DELETE FROM kk_positions WHERE id = %s"
        cursor.execute(query, (id,))

        # Commit the changes
        db.commit()
        cursor.close()

        # Return a success response
        return jsonify({"status": "success", "message": "Position deleted successfully"}), 200

    except Exception as e:
        # Handle errors (e.g., if the position ID doesn't exist or any DB-related errors)
        print("Error occurred:", str(e))  # Log the error message
        return jsonify({"status": "error", "message": str(e)}), 500
        
from datetime import datetime

@app.route('/admin/pages/kk-list')
def kk_list():
    if not session.get('logged_in'):
        flash("Please log in to access the KK List page.", "danger")
        return redirect(url_for('admin_login'))

    # Query the database for all users
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor(dictionary=True)
    try:
        # Fetch admin user details
        username = session.get('username')  # Username stored during login
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

        # Query for all KK profiles with a flag for new registrations
        query = """
        SELECT
            kk_profiles.id_kkprofiles, kk_profiles.first_name, kk_profiles.last_name, kk_profiles.middle_name, kk_profiles.suffix, kk_profiles.birthday, kk_profiles.gender, kk_profiles.email, kk_profiles.phone,
            kk_profiles.purok, kk_profiles.barangay, kk_profiles.municipality, kk_profiles.province, kk_profiles.zipcode, kk_profiles.civil_status, kk_profiles.youth_classification,
            kk_profiles.specific_needs, kk_profiles.youth_age_group, kk_profiles.work_status, kk_profiles.educational_bg, kk_profiles.voter_status, kk_profiles.vote_last_election,
            kk_profiles.attended_kk, kk_profiles.times_attended, kk_profiles.reason_not_attended,
            DATE(kk_profiles.created_at) = CURDATE() AS is_new,  -- Flag for new members
            kk_profiles.created_at  -- For ordering by newest registration
        FROM kk_profiles
        ORDER BY is_new DESC, created_at DESC;  -- Sort by new members first, then by registration date
        """
        cursor.execute(query)
        users = cursor.fetchall()  # Fetch all records from the database

        # Calculate age and assign youth age group for each user
        for user in users:
            if user['birthday']:
                birthdate = user['birthday']  # Already a datetime.date object
                today = datetime.today().date()  # Convert to date object
                age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
                user['age'] = age

                # Determine the youth age group
                if 15 <= age <= 17:
                    user['youth_age_group'] = "Child Youth"
                elif 18 <= age <= 24:
                    user['youth_age_group'] = "Core Youth"
                elif 25 <= age <= 30:
                    user['youth_age_group'] = "Young Adult"
                elif age >= 31:
                    user['youth_age_group'] = "Adult"
                else:
                    user['youth_age_group'] = "N/A"  # Not in the youth age range
            else:
                user['age'] = None  # Handle cases where birthday is missing or invalid
                user['youth_age_group'] = "Unknown"

    finally:
        cursor.close()
        db.close()

    # Render the admin's user list template
    return render_template(
        'admin/pages/kk-list.html',
        users=users,
        first_name=user_details['first_name'],  # Add first name
        last_name=user_details['last_name'],    # Add last name
        admin_details=user_details
    )

@app.route('/update_kk_profile/<int:user_id>', methods=['POST'])
def update_kk_profile(user_id):
    if request.method == 'POST':
        try:
            # Log incoming form data for debugging
            print("Incoming request form data:", request.form)

            # Retrieve form data
            first_name = request.form['name']
            middle_name = request.form['middlename']
            last_name = request.form['lastname']
            suffix = request.form.get('suffix', '')
            birthday = request.form['birthday']
            gender = request.form['gender']
            email = request.form['email']
            phone = request.form['phone']
            purok = request.form['purok']
            barangay = request.form['barangay']
            municipality = request.form['municipality']
            province = request.form['province']
            zipcode = request.form['zipcode']
            civil_status = request.form['civilStatus']
            youth_classification = request.form['youthClassification']
            specific_needs = request.form.get('specificNeeds', None)
            youth_age_group = request.form['youthAgeGroup']
            work_status = request.form['workStatus']
            educational_bg = request.form['educationalbg']
            voter_status = request.form['voterStatus']

            # Connect to the database
            conn = get_db_connection()
            cursor = conn.cursor()

            # SQL Update Query
            query = """
                UPDATE kk_profiles
                SET first_name = %s, middle_name = %s, last_name = %s, suffix = %s, birthday = %s,
                    gender = %s, email = %s, phone = %s, purok = %s, barangay = %s, municipality = %s,
                    province = %s, zipcode = %s, civil_status = %s, youth_classification = %s, specific_needs = %s,
                    youth_age_group = %s, work_status = %s, educational_bg = %s, voter_status = %s
                WHERE id_kkprofiles = %s
            """

            # Execute the update query with form data
            cursor.execute(query, (
                first_name, middle_name, last_name, suffix, birthday, gender, email, phone, purok, barangay,
                municipality, province, zipcode, civil_status, youth_classification, specific_needs,
                youth_age_group, work_status, educational_bg, voter_status, user_id
            ))

            # Commit the transaction
            conn.commit()

            # Close the connection
            cursor.close()
            conn.close()

            # Return a success response
            return jsonify({"status": "success", "message": "Profile updated successfully!"})
        except Exception as e:
            print(f"Error updating profile for user {user_id}: {e}")
            return jsonify({"status": "error", "message": str(e)})

    return jsonify({"status": "error", "message": "Invalid request method"})

@app.route('/delete_kkprofile/<int:id_kkprofiles>', methods=['DELETE'])
def delete_kkprofile(id_kkprofiles):
    try:
        # Debugging the incoming request
        print("Received user ID:", id_kkprofiles)  # Print the user ID from the URL path

        if not id_kkprofiles:
            return jsonify({"status": "error", "message": "User ID is required"}), 400

        # Connect to the database (assuming `get_db_connection()` is your method for DB connection)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the kkprofile from the database (Replace `kkprofiles` with your actual table name)
        query = "DELETE FROM kk_profiles WHERE id_kkprofiles = %s"
        cursor.execute(query, (id_kkprofiles,))

        # Commit the changes
        conn.commit()
        cursor.close()

        # Return a success response
        return jsonify({"status": "success", "message": "Profile deleted successfully"}), 200

    except Exception as e:
        # Handle errors (e.g., if the user ID doesn't exist or any DB-related errors)
        print("Error occurred:", str(e))  # Log the error message
        return jsonify({"status": "error", "message": str(e)}), 500

# Admin Reports Route
@app.route('/admin/pages/charts')
def charts():
    if not session.get('logged_in'):
        flash("Please log in to access the KK List page.", "danger")
        return redirect(url_for('admin_login'))

    # Database connection
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Fetch admin user details
        username = session.get('username')
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

        # Initialize date filters
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')

        # Helper function to append date filters
        def append_date_filters(query, params):
            if from_date:
                query += " created_at >= %s"
                params.append(from_date)
                if to_date:
                    query += " AND"
            if to_date:
                query += " created_at <= %s"
                params.append(to_date)
            return query, params

        # Common query base
        base_query = " WHERE TIMESTAMPDIFF(YEAR, birthday, CURDATE()) BETWEEN 15 AND 30"

        # Function to execute grouped queries
        def execute_grouped_query(select_fields, group_by_field):
            query = f"SELECT {select_fields}, COUNT(*) AS count FROM kk_profiles {base_query}"
            params = []
            if from_date or to_date:
                query += " AND"
                query, params = append_date_filters(query, params)
            query += f" GROUP BY {group_by_field}"
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

        # Query data
        purok_data = execute_grouped_query("purok", "purok")
        purok_data = [{"purok": row["purok"], "count": row["count"]} for row in purok_data]

        age_group_results = execute_grouped_query("purok, youth_age_group", "purok, youth_age_group")
        age_group_data = {}
        for row in age_group_results:
            purok, age_group = row["purok"], row["youth_age_group"]
            if purok not in age_group_data:
                age_group_data[purok] = {}
            age_group_data[purok][age_group] = row["count"]

        voter_status_results = execute_grouped_query("purok, voter_status", "purok, voter_status")
        voter_status_data = {}
        for row in voter_status_results:
            purok, voter_status = row["purok"], row["voter_status"]
            if purok not in voter_status_data:
                voter_status_data[purok] = {}
            voter_status_data[purok][voter_status] = row["count"]

        work_status_results = execute_grouped_query("purok, work_status", "purok, work_status")
        work_status_data = {}
        for row in work_status_results:
            purok, work_status = row["purok"], row["work_status"]
            if purok not in work_status_data:
                work_status_data[purok] = {}
            work_status_data[purok][work_status] = row["count"]

        vote_last_election_results = execute_grouped_query("purok, vote_last_election", "purok, vote_last_election")
        vote_last_elections = ['No', 'Yes']
        vote_last_election_data = {}
        for row in vote_last_election_results:
            purok, vote_last_election = row["purok"], row["vote_last_election"]
            if purok not in vote_last_election_data:
                vote_last_election_data[purok] = {vle: 0 for vle in vote_last_elections}
            vote_last_election_data[purok][vote_last_election] = row["count"]

        gender_results = execute_grouped_query("purok, gender", "purok, gender")
        gender_data = {}
        for row in gender_results:
            purok, gender = row["purok"], row["gender"]
            if purok not in gender_data:
                gender_data[purok] = {}
            gender_data[purok][gender] = row["count"]

        classification_results = execute_grouped_query("purok, youth_classification", "purok, youth_classification")
        classification_data = {}
        for row in classification_results:
            purok, youth_classification = row["purok"], row["youth_classification"]
            if purok not in classification_data:
                classification_data[purok] = {}
            classification_data[purok][youth_classification] = row["count"]

             # Fetch civil status data grouped by purok
        civil_status_results = execute_grouped_query("purok, civil_status", "purok, civil_status")
        civil_status_data = {}
        for row in civil_status_results:
            purok, civil_status = row["purok"], row["civil_status"]
            if purok not in civil_status_data:
                civil_status_data[purok] = {}
            civil_status_data[purok][civil_status] = row["count"]

    finally:
        cursor.close()
        db.close()

    return render_template(
        'admin/pages/charts.html',
        first_name=user_details['first_name'],
        last_name=user_details['last_name'],
        purok_data=purok_data,
        age_group_data=age_group_data,
        voter_status_data=voter_status_data,
        work_status_data=work_status_data,
        vote_last_election_data=vote_last_election_data,
        gender_data=gender_data,
        classification_data=classification_data,
        civil_status_data=civil_status_data,
        from_date=from_date,
        to_date=to_date
    )
# Admin SK Achievement Route
@app.route('/admin/pages/achievements')
def achievements():
    if not session.get('logged_in'):
        flash("Please log in to access the SK Officials page.", "danger")
        return redirect(url_for('admin_login'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)  # Use dictionary=True for easier access to columns by name
    try:
        # Fetch admin user details
        username = session.get('username')  # Username stored during login
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

        # Modified query: Get multiple images per project (grouped by project_id)
        query = """
            SELECT 
                pa.id_project,
                pa.project_name,
                pa.project_location,
                pa.date_achieved,
                pa.project_details,
                pa.date_started,
                GROUP_CONCAT(pi.image_url) AS image_urls
            FROM 
                project_achievements pa
            LEFT JOIN 
                project_images pi ON pa.id_project = pi.project_id
            GROUP BY 
                pa.id_project
        """
        cursor.execute(query)
        achievements = cursor.fetchall()  # Fetch all achievements with multiple image URLs

    finally:   
        cursor.close()
        db.close()

    return render_template('admin/pages/achievements.html', 
        first_name=user_details['first_name'],
        last_name=user_details['last_name'],
        achievements=achievements)

# Configuration for file uploads
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to add a new achievement
@app.route('/add_achievement', methods=['POST'])
def add_achievement():
    # Get data from the request
    project_name = request.form.get('project_name')
    project_details = request.form.get('project_details')
    date_started = request.form.get('date_started')
    date_achieved = request.form.get('date_achieved')
    project_location = request.form.get('project_location')

    # Validate the data
    if not project_name or not project_details or not date_achieved:
        return jsonify({"error": "All fields are required."}), 400
    
    # Handle file upload
    files = request.files.getlist('img[]')  # Get all uploaded files
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    image_urls = []
    for file in files:
        if not allowed_file(file.filename):
            return jsonify({"error": f"Invalid file type for {file.filename}."}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            # Ensure directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

            # Save the file
            file.save(filepath)
            print(f"File saved successfully at {filepath}")

            # Construct relative URL for each file
            relative_url = f"/static/uploads/{filename}"
            image_urls.append(relative_url)
        except Exception as e:
            print(f"Error saving file {file.filename}: {str(e)}")
            return jsonify({"error": f"Error saving file {file.filename}."}), 500

    # Save the project details to the `project_achievements` table
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Insert project details
        query = """
            INSERT INTO project_achievements 
            (project_name, project_details, date_started, date_achieved, project_location) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (project_name, project_details, date_started, date_achieved, project_location))
        db.commit()

        # Get the project ID of the newly inserted project
        project_id = cursor.lastrowid

        # Insert each image URL into the `project_images` table
        for image_url in image_urls:
            cursor.execute("""
                INSERT INTO project_images (project_id, image_url)
                VALUES (%s, %s)
            """, (project_id, image_url))
        db.commit()

        return jsonify({
            "success": True,
            "message": "Achievement added successfully!",
            "image_urls": image_urls
        }), 201

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'db' in locals() and db:
            db.close()
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS            

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

from datetime import datetime
@app.route('/update_project', methods=['POST'])
def update_project():
    conn = None  # Initialize conn outside try block to avoid UnboundLocalError
    try:
        # Extract form data
        project_id = request.form['id_project']
        project_name = request.form['project_name']
        project_location = request.form['project_location']
        date_started = request.form['date_started']  # Expecting a string in YYYY-MM-DD format
        date_achieved = request.form['date_achieved']  # Expecting a string in YYYY-MM-DD format
        project_details = request.form['project_details']

        # Ensure date_achieved is a valid string in the expected format (optional)
        if not date_achieved:
            return jsonify({"status": "error", "message": "Date achieved is required."}), 400
        
        # Handle file uploads
        image_urls = []
        if 'project_images' in request.files:
            image_files = request.files.getlist('project_images')
            for image_file in image_files:
                if image_file.filename != '':
                    # Generate unique filename using project_id and secure_filename
                    unique_filename = f"{project_id}_{secure_filename(image_file.filename)}"
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    image_file.save(image_path)
                    image_urls.append(f"/static/uploads/{unique_filename}")  # Use relative URL

        # Database operations
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        # Update project details (storing date_achieved as string directly)
        query = """
            UPDATE project_achievements
            SET project_name=%s, project_location=%s, date_started=%s, date_achieved=%s, project_details=%s
            WHERE id_project=%s
        """
        cursor.execute(query, (project_name, project_location,  date_started, date_achieved, project_details, project_id))

        # Check for existing images in project_images and add only new ones
        if image_urls:
            for image_url in image_urls:
                # Check if the image already exists for this project
                cursor.execute("""
                    SELECT 1 FROM project_images WHERE project_id = %s AND image_url = %s
                """, (project_id, image_url))
                existing_image = cursor.fetchone()

                if not existing_image:
                    # If the image does not already exist, insert it
                    cursor.execute("""
                        INSERT INTO project_images (project_id, image_url)
                        VALUES (%s, %s)
                    """, (project_id, image_url))

        conn.commit()  # Commit all changes
    except Exception as e:
        print(f"Error updating project: {e}")
        if conn:
            conn.rollback()  # Ensure rollback if conn exists
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            conn.close()  # Only close conn if it was created

    # Return success response
    return jsonify({"status": "success", "message": "Project updated successfully."}), 200

from flask import jsonify, request
import json

@app.route('/delete_project/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    try:
        # Debugging the incoming request
        print("Received project ID:", project_id)  # Print the project ID from the URL path

        if not project_id:
            return jsonify({"status": "error", "message": "Project ID is required"}), 400

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the project from the database
        query = "DELETE FROM project_achievements WHERE id_project = %s"
        cursor.execute(query, (project_id,))

        # Commit the changes
        conn.commit()
        cursor.close()

        # Return a success response
        return jsonify({"status": "success", "message": "Project deleted successfully"}), 200

    except Exception as e:
        # Handle errors (e.g., if the project ID doesn't exist)
        print("Error occurred:", str(e))  # Log the error message
        return jsonify({"status": "error", "message": str(e)}), 500

import logging
logging.basicConfig(level=logging.DEBUG)
from datetime import datetime

# Define base directory and upload folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/save_pdf', methods=['POST'])
def save_pdf():
    if 'pdf_file' not in request.files:
        logging.error("No file part in the request")
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    if pdf_file.filename == '':
        logging.error("No file selected for upload")
        return jsonify({'success': False, 'message': 'No selected file'}), 400

    # Get report name from the form
    report_name = request.form.get('report_name', 'Untitled Report')

    # Assume user_id is stored in session after login
    user_id = session.get('user_id')
    if not user_id:
        logging.error("User not authenticated")
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401

    try:
        # Query admin_users table for first_name and last_name
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT first_name, last_name FROM admin_users WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            logging.error("User not found in admin_users")
            return jsonify({'success': False, 'message': 'User not found'}), 404

        first_name, last_name = user
        exported_by = f"{first_name} {last_name}"

        # Save the PDF file
        filename = secure_filename(pdf_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(file_path)
        logging.info(f"File saved to {file_path}")

        # Save export details in the database
        export_date = datetime.now()
        cursor.execute("""
            INSERT INTO export_logs (file_name, file_path, export_date, report_name, exported_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, file_path, export_date, report_name, exported_by))
        db.commit()
        cursor.close()
        db.close()

        logging.info("File information saved to database")
        return jsonify({'success': True, 'message': 'PDF saved successfully!'})
    except Exception as e:
        logging.error("Error saving PDF: %s", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/admin/pages/export')
def export():
    if not session.get('logged_in'):
        flash("Please log in to access the SK Officials page.", "danger")
        return redirect(url_for('admin_login'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)  # Use dictionary=True for easier access to columns by name

    try:
        # Fetch admin user details
        username = session.get('username')  # Username stored during login
        cursor.execute("SELECT first_name, last_name FROM admin_users WHERE username = %s", (username,))
        user_details = cursor.fetchone()

        if not user_details:
            flash("Admin user details not found.", "danger")
            return redirect(url_for('admin_login'))

        # Fetch export logs with newest first
        cursor.execute("SELECT id, file_name, export_date, exported_by FROM export_logs ORDER BY id DESC")  
        export = cursor.fetchall()

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        export = []  # Default to an empty list in case of an error

    finally:
        cursor.close()
        db.close()

    return render_template('admin/pages/export.html', 
        first_name=user_details['first_name'],
        last_name=user_details['last_name'],
        export=export)

# New delete route
@app.route('/admin/pages/export/delete/<int:id>', methods=['DELETE'])
def delete_export(id):
    try:
        db = get_db_connection()  # Replace with your actual DB connection function
        cursor = db.cursor()

        # Delete the record with the provided id
        cursor.execute("DELETE FROM export_logs WHERE id = %s", (id,))
        db.commit()

        cursor.close()
        db.close()

        # Return a success response for AJAX
        return jsonify({'success': True, 'message': 'Export record deleted successfully.'}), 200
    except Exception as e:
        # Handle errors
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete the export record.'}), 500

#CLIENT======================================================================================>>
@app.route('/')
def index():

    return render_template('index.html')
@app.route('/check-username', methods=['GET'])
def check_username():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()

    username = request.args.get('username')  # Get the username from the query parameter

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    try:
        # Check if the username already exists in the kk_users table (case-insensitive)
        cursor.execute("SELECT * FROM kk_users WHERE LOWER(kk_username) = LOWER(%s)", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'available': False})  # Username is taken
        else:
            return jsonify({'available': True})  # Username is available
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()

from werkzeug.security import generate_password_hash

from werkzeug.security import generate_password_hash
from flask import render_template, request, redirect, url_for

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()

    if request.method == 'POST':
        # Fetch form data
        kk_username = request.form.get('username')
        kk_password = request.form.get('password')
        kk_confirm_password = request.form.get('confirmPassword')
        firstname = request.form.get('firstname')
        middlename = request.form.get('middlename')
        lastname = request.form.get('lastname')

        # Check if passwords match
        if kk_password != kk_confirm_password:
            return render_template('signup.html', error_message="Passwords do not match, please try again.")

        # Check if username is already taken (case insensitive)
        cursor.execute("SELECT * FROM kk_users WHERE LOWER(kk_username) = LOWER(%s)", (kk_username,))
        existing_user = cursor.fetchone()
        if existing_user:
            return render_template('signup.html', username_taken=True)

        # Check if the combination of first, middle, and last name already exists (case-insensitive)
        cursor.execute("""
            SELECT * FROM kk_profiles
            WHERE LOWER(first_name) = LOWER(%s) 
            AND LOWER(middle_name) = LOWER(%s) 
            AND LOWER(last_name) = LOWER(%s)
        """, (firstname, middlename, lastname))

        existing_profile = cursor.fetchone()
        if existing_profile:
            return render_template('signup.html', name_exists=True)

        try:
            # Hash the password before saving it to the database
            hashed_password = generate_password_hash(kk_password)

            # Insert the user into `kk_users` table with the hashed password
            user_query = """
                INSERT INTO kk_users (kk_username, kk_password, profile_complete)
                VALUES (%s, %s, %s)
            """
            user_values = (kk_username, hashed_password, False)
            cursor.execute(user_query, user_values)
            db.commit()

            # Get the last inserted ID (this will be `id_kk`)
            user_id = cursor.lastrowid

            # Insert user profile into `kk_profiles` table with `id_kkprofiles` matching `id_kk`
            profile_query = """
                INSERT INTO kk_profiles (id_kkprofiles, first_name, middle_name, last_name)
                VALUES (%s, %s, %s, %s)
            """
            profile_values = (user_id, firstname, middlename, lastname)
            cursor.execute(profile_query, profile_values)
            db.commit()

            # Redirect to profile creation page with `id_kkprofiles`
            return redirect(url_for('register', id_kkprofiles=user_id))

        except Exception as e:
            db.rollback()
            return render_template('signup.html', error_message=f"An error occurred: {e}")

        finally:
            cursor.close()
            db.close()

    # If method is GET or no errors
    return render_template('signup.html', name_exists=False, username_taken=False)

def calculate_youth_age_group(birthday):
    """
    Calculate the youth age group based on the given birthday.
    """
    if not birthday:
        raise ValueError("Birthday is required")

    try:
        # Convert the birthday to a datetime object
        birth_date = datetime.strptime(birthday, "%Y-%m-%d")
    except ValueError:
        # Handle case where the birthday is in an invalid format
        raise ValueError("Invalid birthday format. Please use YYYY-MM-DD.")
    
    today = datetime.now()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if 15 <= age <= 17:
        return "Child Youth"
    elif 18 <= age <= 24:
        return "Core Youth"
    elif 25 <= age <= 30:
        return "Young Adult"
    return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()

    # Retrieve id_kkprofiles from query string or form data
    id_kkprofiles = request.args.get('id_kkprofiles') or request.form.get('id_kkprofiles')

    if not id_kkprofiles:
        print("Error: id_kkprofiles is missing from the query parameters.")
        return "Error: Missing id_kkprofiles parameter.", 400

    # Fetch first_name, middle_name, and last_name from the kk_profiles table
    try:
        query = "SELECT first_name, middle_name, last_name FROM kk_profiles WHERE id_kkprofiles = %s"
        cursor.execute(query, (id_kkprofiles,))
        user_data = cursor.fetchone()

        if not user_data:
            print(f"No record found in kk_profiles for id_kkprofiles: {id_kkprofiles}")
            return "Error: User not found.", 404

        # Extract the name data
        first_name, middle_name, last_name = user_data
        print(f"Fetched User Data - ID: {id_kkprofiles}, First Name: {first_name}, Middle Name: {middle_name}, Last Name: {last_name}")
    except Exception as e:
        print(f"Database Error while fetching user data: {e}")
        return f"Database error: {e}", 500

    if request.method == 'POST':
        # Debug: Log form submission
        print("Form submitted via POST method")

        # Retrieve the rest of the form data (the user has already inputted username and password during signup)
        suffix = request.form.get('suffix')
        birthday = request.form.get('birthdayDate')
        gender = request.form.get('inlineRadioOptions')
        email = request.form.get('emailAddress')
        phone = request.form.get('phoneNumber')
        purok = request.form.get('purok')
        barangay = request.form.get('barangay')
        municipality = request.form.get('municipality')
        province = request.form.get('province')
        zipcode = request.form.get('zipcode')
        civil_status = request.form.get('civilStatus')
        youth_classification = request.form.get('youthClassification')
        specific_needs = request.form.get('specificNeeds')
        youth_age_group = request.form.get('youthAgeGroup')  # Submitted from frontend
        work_status = request.form.get('workStatus')
        educational_bg = request.form.get('educationalbg')
        voter_status = request.form.get('voterStatus')
        vote_last_election = request.form.get('voteLastElection')
        attended_kk = request.form.get('attendedKK')
        times_attended = request.form.get('timesAttended')
        reason_not_attended = request.form.get('reasonNotAttended')

        # Debug: Log form data
        print(f"Form Data: {request.form}")

        # Validate and recalculate the youth age group based on birthday
        try:
            calculated_youth_age_group = calculate_youth_age_group(birthday)
            if calculated_youth_age_group != youth_age_group:
                # Debug: Log age group mismatch
                print(f"Age Group Mismatch: Frontend ({youth_age_group}), Calculated ({calculated_youth_age_group})")
                youth_age_group = calculated_youth_age_group  # Overwrite to ensure consistency
        except Exception as e:
            print(f"Error calculating youth age group: {e}")
            return f"Error calculating age group: {e}", 400

        # Insert into `kk_profiles` using the existing id_kkprofiles
        query = """
        UPDATE kk_profiles 
        SET 
            suffix = %s, birthday = %s, gender = %s, email = %s, phone = %s,
            purok = %s, barangay = %s, municipality = %s, province = %s, zipcode = %s, 
            civil_status = %s, youth_classification = %s, specific_needs = %s, 
            youth_age_group = %s, work_status = %s, educational_bg = %s, 
            voter_status = %s, vote_last_election = %s, attended_kk = %s, 
            times_attended = %s, reason_not_attended = %s
        WHERE id_kkprofiles = %s
        """
        values = (
            suffix, birthday, gender, email, phone, purok, barangay, municipality,
            province, zipcode, civil_status, youth_classification, specific_needs,
            youth_age_group, work_status, educational_bg, voter_status, vote_last_election,
            attended_kk, times_attended, reason_not_attended, id_kkprofiles
        )

        # Debug: Log query and values before execution
        print(f"Executing Query: {query}")
        print(f"With Values: {values}")

        try:
            cursor.execute(query, values)
            db.commit()
            # Debug: Log successful database update
            print("Profile data successfully updated in database")
        except Exception as e:
            db.rollback()
            print(f"Database Error: {e}")
            return f"Database error: {e}", 500

        # Redirect to confirmation page
        cursor.close()
        db.close()
        print(f"Redirecting to confirmation page for {first_name}")
        return redirect(url_for('confirmation', name=first_name))

    # Debug: Log when rendering the form
    print("Rendering form page")
    cursor.close()
    db.close()

    # Pass first, middle, and last name to pre-populate the form (only for display purposes)
    return render_template(
        'form.html',
        id_kkprofiles=id_kkprofiles,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name
    )

@app.route('/confirmation')
def confirmation():
    name = request.args.get('name', 'User')  # Retrieve name from query parameters
    return render_template('confirmation.html', name=name)

# Login route
from werkzeug.security import check_password_hash

@app.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()
    
    if request.method == 'POST':
        # Collect login credentials
        kk_username = request.form.get('username')  # Match the name attribute in your HTML
        kk_password = request.form.get('password')

        # Validate credentials (fetch the hashed password from DB)
        query = "SELECT id_kk, kk_password FROM kk_users WHERE kk_username = %s"
        cursor.execute(query, (kk_username,))
        user = cursor.fetchone()

        if user:
            # Check if the password matches the hashed password
            stored_hashed_password = user[1]
            if check_password_hash(stored_hashed_password, kk_password):
                # Password is correct
                session['username'] = kk_username
                session['id_kk'] = user[0]  # Save user ID in session for easier profile lookup
                return redirect(url_for('profile'))  # Redirect to the profile page
            else:
                # Password is incorrect
                return render_template('login.html', error="Invalid username or password")
        else:
            # Username doesn't exist
            return render_template('login.html', error="Invalid username or password")
    
    cursor.close()
    db.close()
    return render_template('login.html')


@app.route('/profile')
def profile():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()
    if 'id_kk' not in session:
        cursor.close()  # Close cursor
        db.close()      # Close DB connection
        return redirect(url_for('login'))

    user_id = session['id_kk']
    query = """
        SELECT * FROM kk_profiles 
        INNER JOIN kk_users ON kk_profiles.id_kkprofiles = kk_users.id_kk 
        WHERE kk_users.id_kk = %s 
        ORDER BY kk_profiles.id_kkprofiles DESC 
        LIMIT 1
    """

    try:
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        print("User Data:", user)
    except Exception as e:
        print("Error fetching user profile:", str(e))
        user = None
    finally:
        cursor.close()  # Close cursor
        db.close()      # Close DB connection

    if user:
        return render_template('profile.html', user=user)
    else:
        return render_template('profile.html', error="No profile found.")

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    db = get_db_connection()  # Get DB connection
    cursor = db.cursor()
    if 'id_kk' not in session:
        
        return redirect(url_for('login'))

    user_id = session['id_kk']
    
    # Fetch the existing profile data from the database
    query = """
        SELECT * FROM kk_profiles 
        INNER JOIN kk_users ON kk_profiles.id_kkprofiles = kk_users.id_kk 
        WHERE kk_users.id_kk = %s 
        ORDER BY kk_profiles.id_kkprofiles DESC 
        LIMIT 1
    """
    cursor.execute(query, (user_id,))
    user = cursor.fetchone()

    if request.method == 'POST':
        # Get form data from POST request
        first_name = request.form['firstName']
        middle_name = request.form['middleName']
        last_name = request.form['lastName']
        suffix = request.form['suffix']
        birthday = request.form['birthday']
        gender = request.form['gender']
        email = request.form['email']
        phone = request.form['phone']
        purok = request.form['purok']
        barangay = request.form['barangay']
        municipality = request.form['municipality']
        province = request.form['province']
        zipcode = request.form['zipcode']
        civil_status = request.form['civil_status']
        youth_classification = request.form['youth_classification']
        specific_needs = request.form['specific_needs']
        youth_age_group = request.form['youth_age_group']
        work_status = request.form['work_status']
        educational_bg = request.form['education']
        voter_status = request.form['voter_status']
        vote_last_election = request.form['voted_last_election']
        attended_kk = request.form['attended_kk']
        times_attended = request.form['times_attended']
        reason_not_attended = request.form['reason_not_attended']

        # Update the user profile in the database
        update_query = """
            UPDATE kk_users
            JOIN kk_profiles ON kk_users.id_kk = kk_profiles.id_kkprofiles
            SET
                kk_profiles.first_name = %s,
                kk_profiles.middle_name = %s,
                kk_profiles.last_name = %s,
                kk_profiles.suffix = %s,
                kk_profiles.birthday = %s,
                kk_profiles.gender = %s,
                kk_profiles.email = %s,
                kk_profiles.phone = %s,
                kk_profiles.purok = %s,
                kk_profiles.barangay = %s,
                kk_profiles.municipality = %s,
                kk_profiles.province = %s,
                kk_profiles.zipcode = %s,
                kk_profiles.civil_status = %s,
                kk_profiles.youth_classification = %s,
                kk_profiles.specific_needs = %s,
                kk_profiles.youth_age_group = %s,
                kk_profiles.work_status = %s,
                kk_profiles.educational_bg = %s,
                kk_profiles.voter_status = %s,
                kk_profiles.vote_last_election = %s,
                kk_profiles.attended_kk = %s,
                kk_profiles.times_attended = %s,
                kk_profiles.reason_not_attended = %s
            WHERE kk_users.id_kk = %s
        """
        try:
            cursor.execute(update_query, (
                first_name, middle_name, last_name, suffix, birthday, gender,
                email, phone, purok, barangay, municipality, province, zipcode,
                civil_status, youth_classification, specific_needs, youth_age_group,
                work_status, educational_bg, voter_status, vote_last_election,
                attended_kk, times_attended, reason_not_attended, user_id
            ))
            db.commit()  # Commit the transaction
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('edit_profile'))
        except Exception as e:
            db.rollback()  # Rollback in case of error
            flash(f'Error updating profile: {e}', 'error')
    cursor.close()
    db.close()
    return render_template('edit_profile.html', user=user)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
