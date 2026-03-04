from flask import (
    render_template, redirect, url_for, flash,
    request, make_response, jsonify
)
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Task, TaskDependency
from app.forms import RegistrationForm, LoginForm, TaskForm
from app.schema import ensure_sqlite_schema
from datetime import datetime
from urllib.parse import urlparse, urljoin
from sqlalchemy.exc import OperationalError
import csv
from io import StringIO


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def register_routes(app):

    # ================= HOME =================
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html')


    # ================= REGISTER =================
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html', form=form)


    # ================= LOGIN =================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()

            if user and user.check_password(form.password.data):
                login_user(user)
                next_page = request.args.get('next')

                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('dashboard')

                flash('Logged in successfully!', 'success')
                return redirect(next_page)

            flash('Invalid username or password.', 'danger')

        return render_template('login.html', form=form)


    # ================= LOGOUT =================
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out successfully.', 'info')
        return redirect(url_for('index'))


    # ================= PROFILE =================
    @app.route('/profile')
    @login_required
    def profile():

        tasks = Task.query.filter_by(user_id=current_user.id).all()

        stats = {
            "total": len(tasks),
            "completed": sum(1 for t in tasks if t.status == "completed"),
            "pending": sum(1 for t in tasks if t.status == "pending"),
            "overdue": sum(
                1 for t in tasks
                if t.status != "completed"
                and t.due_date
                and t.due_date < datetime.utcnow()
            ),
        }

        # Build completion history grouped by day for charts & calendar
        completion_counts = {}
        day_tasks = {}
        for t in tasks:
            if t.completed_at:
                day = t.completed_at.date()
                completion_counts[day] = completion_counts.get(day, 0) + 1
                key = day.strftime("%Y-%m-%d")
                day_tasks.setdefault(key, []).append({
                    "title": t.title,
                    "category": t.category,
                    "priority": t.priority_label,
                })

        history = [
            {"date": day.strftime("%Y-%m-%d"), "completed": count}
            for day, count in sorted(completion_counts.items())
        ]

        stats["history"] = history

        # Gamification: simple streak + level
        unique_days = sorted({h["date"] for h in history})
        streak_days = 0
        if unique_days:
            # count backwards from most recent day as long as days are consecutive
            from datetime import date, timedelta
            last = datetime.strptime(unique_days[-1], "%Y-%m-%d").date()
            streak_days = 1
            for prev in reversed(unique_days[:-1]):
                d = datetime.strptime(prev, "%Y-%m-%d").date()
                if (last - d) == timedelta(days=1):
                    streak_days += 1
                    last = d
                else:
                    break

        stats["streak_days"] = streak_days

        completed = stats["completed"]
        if completed >= 50:
            level = "Legend"
            next_level_at = None
        elif completed >= 25:
            level = "Pro"
            next_level_at = 50
        elif completed >= 10:
            level = "Regular"
            next_level_at = 25
        elif completed >= 5:
            level = "Starter"
            next_level_at = 10
        else:
            level = "Newbie"
            next_level_at = 5

        stats["level"] = level
        stats["next_level_at"] = next_level_at

        return render_template("profile.html", stats=stats, day_tasks=day_tasks)


    # ================= DASHBOARD =================
    @app.route('/dashboard')
    @login_required
    def dashboard():

        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        category_filter = request.args.get('category', 'all')

        query = Task.query.filter_by(user_id=current_user.id)

        if status_filter != 'all':
            query = query.filter_by(status=status_filter)

        if priority_filter != 'all':
            try:
                query = query.filter_by(priority=int(priority_filter))
            except ValueError:
                priority_filter = 'all'

        if category_filter != 'all':
            query = query.filter_by(category=category_filter)

        sort_by = request.args.get('sort', 'priority')

        if sort_by == 'due_date':
            query = query.order_by(Task.due_date.asc().nullslast())
        elif sort_by == 'created':
            query = query.order_by(Task.created_at.desc())
        elif sort_by == 'title':
            query = query.order_by(Task.title.asc())
        else:
            query = query.order_by(
                Task.priority.desc(),
                Task.due_date.asc().nullslast()
            )

        try:
            tasks = query.all()
        except OperationalError:
            # Auto-heal older SQLite DBs after model changes.
            db.session.rollback()
            ensure_sqlite_schema(db)
            tasks = query.all()

        categories = db.session.query(Task.category).filter_by(
            user_id=current_user.id
        ).distinct().all()

        categories = [c[0] for c in categories if c[0]]

        total_tasks = Task.query.filter_by(user_id=current_user.id).count()
        completed_tasks = Task.query.filter_by(
            user_id=current_user.id, status='completed'
        ).count()
        pending_tasks = Task.query.filter_by(
            user_id=current_user.id, status='pending'
        ).count()

        overdue_tasks = Task.query.filter(
            Task.user_id == current_user.id,
            Task.status != 'completed',
            Task.due_date != None,
            Task.due_date < datetime.utcnow()
        ).count()

        stats = {
            'total': total_tasks,
            'completed': completed_tasks,
            'pending': pending_tasks,
            'overdue': overdue_tasks
        }

        milestones = [t for t in tasks if t.is_milestone]

        return render_template(
            'dashboard.html',
            tasks=tasks,
            milestones=milestones,
            categories=categories,
            stats=stats,
            status_filter=status_filter,
            priority_filter=priority_filter,
            category_filter=category_filter,
            sort_by=sort_by
        )

    # ================= GANTT VIEW =================
    @app.route('/gantt')
    @login_required
    def gantt_view():
        tasks = Task.query.filter_by(user_id=current_user.id).all()

        gantt_tasks = []
        for t in tasks:
            gantt_tasks.append({
                "id": t.id,
                "title": t.title,
                "is_milestone": bool(getattr(t, "is_milestone", False)),
                "status": t.status,
                "priority": t.priority,
                "percent_complete": getattr(t, "percent_complete", 0) or 0,
                "start": t.created_at.isoformat() if t.created_at else None,
                "end": t.due_date.isoformat() if t.due_date else None,
            })

        return render_template('gantt.html', tasks=tasks, gantt_tasks=gantt_tasks)

    @app.route('/gantt/dependencies', methods=['GET'])
    @login_required
    def gantt_dependencies():
        deps = TaskDependency.query.join(TaskDependency.predecessor).filter(
            TaskDependency.predecessor.has(user_id=current_user.id)
        ).all()
        return jsonify([
            {
                "id": d.id,
                "predecessor_id": d.predecessor_id,
                "successor_id": d.successor_id,
                "type": d.dependency_type,
            }
            for d in deps
        ])

    @app.route('/gantt/dependencies', methods=['POST'])
    @login_required
    def create_gantt_dependency():
        data = request.get_json(force=True)
        predecessor_id = data.get('predecessor_id')
        successor_id = data.get('successor_id')
        dependency_type = data.get('type', 'FS')

        if not predecessor_id or not successor_id:
            return jsonify({"success": False, "error": "Missing task ids"}), 400

        if dependency_type not in ('FS', 'SS', 'SF', 'FF'):
            return jsonify({"success": False, "error": "Invalid dependency type"}), 400

        predecessor = Task.query.get_or_404(predecessor_id)
        successor = Task.query.get_or_404(successor_id)

        # Ensure tasks belong to current user
        if predecessor.user_id != current_user.id or successor.user_id != current_user.id:
            return jsonify({"success": False}), 403

        dep = TaskDependency(
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dependency_type=dependency_type
        )
        db.session.add(dep)
        db.session.commit()

        return jsonify({
            "success": True,
            "id": dep.id,
        })


    # ================= ADD TASK =================
    @app.route('/task/new', methods=['GET', 'POST'])
    @login_required
    def add_task():

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip() or None
            priority = request.form.get('priority', type=int) or 2
            due_date_str = request.form.get('due_date') or ''

            due_date = None
            if due_date_str:
                # HTML datetime-local uses "YYYY-MM-DDTHH:MM"
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    flash('Could not understand the due date, please use the date picker.', 'warning')

            if title:
                task = Task(
                    title=title,
                    description=description or None,
                    priority=priority,
                    category=category,
                    due_date=due_date,
                    user_id=current_user.id
                )
                db.session.add(task)
                db.session.commit()
                flash('Task added successfully!', 'success')
                return redirect(url_for('dashboard'))

        return render_template('add_task.html')


    # ================= EDIT TASK =================
    @app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_task(task_id):

        task = Task.query.get_or_404(task_id)

        if task.user_id != current_user.id:
            flash('You cannot edit this task.', 'danger')
            return redirect(url_for('dashboard'))

        form = TaskForm(obj=task)

        if form.validate_on_submit():
            task.title = form.title.data
            task.description = form.description.data
            task.priority = form.priority.data
            task.category = form.category.data
            task.due_date = form.due_date.data
            task.status = form.status.data

            if task.status == 'completed' and not task.completed_at:
                task.completed_at = datetime.utcnow()
            elif task.status != 'completed':
                task.completed_at = None

            db.session.commit()
            flash('Task updated successfully!', 'success')
            return redirect(url_for('dashboard'))

        return render_template('edit_task.html', form=form, task=task)


    # ================= DELETE TASK (AJAX) =================
    @app.route('/task/<int:task_id>/delete', methods=['POST'])
    @login_required
    def delete_task(task_id):

        task = Task.query.get_or_404(task_id)

        if task.user_id != current_user.id:
            return jsonify({"success": False}), 403

        db.session.delete(task)
        db.session.commit()

        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.accept_mimetypes['application/json']
            >= request.accept_mimetypes['text/html']
        )

        if wants_json:
            return jsonify({"success": True})

        flash('Task deleted.', 'info')
        return redirect(url_for('dashboard'))


    # ================= TOGGLE TASK (AJAX) =================
    @app.route('/task/<int:task_id>/toggle', methods=['POST'])
    @login_required
    def toggle_task_status(task_id):

        task = Task.query.get_or_404(task_id)

        if task.user_id != current_user.id:
            return jsonify({"success": False}), 403

        if task.status == 'completed':
            task.status = 'pending'
            task.completed_at = None
        else:
            task.status = 'completed'
            task.completed_at = datetime.utcnow()

        db.session.commit()

        # If this is an AJAX/JSON request, return JSON so the frontend
        # can update the UI without a full page reload.
        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.accept_mimetypes['application/json']
            >= request.accept_mimetypes['text/html']
        )

        if wants_json:
            return jsonify({
                "success": True,
                "new_status": task.status
            })

        # Fallback for normal form submissions: just go back to dashboard.
        flash('Task status updated.', 'success')
        return redirect(url_for('dashboard'))


    # ================= EXPORT CSV =================
    @app.route('/export/tasks')
    @login_required
    def export_tasks():

        tasks = Task.query.filter_by(
            user_id=current_user.id
        ).order_by(Task.created_at.desc()).all()

        si = StringIO()
        writer = csv.writer(si)

        writer.writerow([
            'Title', 'Description', 'Priority', 'Status',
            'Category', 'Due Date', 'Created', 'Completed'
        ])

        for task in tasks:
            writer.writerow([
                task.title,
                task.description or '',
                task.priority_label,
                task.status,
                task.category or '',
                task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else '',
                task.created_at.strftime('%Y-%m-%d %H:%M'),
                task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else ''
            ])

        output = make_response(si.getvalue())
        output.headers['Content-Disposition'] = 'attachment; filename=tasks.csv'
        output.headers['Content-type'] = 'text/csv'

        return output