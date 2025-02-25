import smtplib

def send_email_via_gmail(receiver_email, subject, body):
    gmail_user = 'taltub123@gmail.com'
    gmail_password = 'vcvo vyjk fgwh iuda'

    email_text = f"""From: {gmail_user}\nTo: {receiver_email}\nSubject: {subject}\n\n{body}"""
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, receiver_email, email_text)
        server.quit()
        print('Email sent!')
    except Exception as e:
        print('Failed to send email:', e)