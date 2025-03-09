from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.SignUpView.as_view(), name="sign_up"), # Регистрация пользователя
    path("login/", views.LogInView.as_view(), name="login"), # Авторизация пользователя
    path("send-otp/", views.SendOTPView.as_view(), name="send_otp"), # Отправка OTP
    path("verify-otp/", views.VerifyOTPView.as_view(), name="verify_otp"), # Подтверждение номера телефона
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset_password"), # Сброс пароля
    path("profile/", views.ProfileView.as_view(), name="profile"), # Профиль пользователя
    path("set-password/", views.SetPasswordView.as_view(), name="set_password"), # Установка пароля
    path("password/change/", views.UserPasswordChangeAPI.as_view(), name="change-password"),
    path("send-egov_code/", views.SendCodeBiometryView.as_view(), name="send-egov_code"),
]
