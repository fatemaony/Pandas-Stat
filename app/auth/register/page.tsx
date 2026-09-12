import { RegisterForm } from "@/components/auth-ui/register-form"
import { ReturnButton } from "@/components/return-button"
import { SignInOauthButton } from "@/components/auth-ui/sign-in-oauth-button"
import Link from "next/link"


function Page() {
    return (
        <div className="mx-auto h-svh w-full mt-10">
            <ReturnButton href="/" label="Brand Name" />

            <div className="max-w-md mx-auto bg-gray-100 p-10 rounded-md shadow-sm">
                <h1 className="text-5xl font-bold text-center mb-10">Register</h1>
                <RegisterForm />
                <p className="text-center text-gray-500 mt-4">Already have an account? <Link className="text-blue-500 hover:underline" href="/auth/signin">Sign In</Link></p>
                <hr className="max-w-sm" />
                <div className="flex max-w-sm gap-3 pt-5">
                    <SignInOauthButton provider="google" signUp />
                    <SignInOauthButton provider="github" signUp />
                </div>
            </div>
        </div>
    )
}
export default Page 