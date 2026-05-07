// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#include "WidgetBlueprintGeneratorCommandlet.h"

#include "EditorAssetLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "WidgetBlueprintGeneratorLibrary.h"

namespace
{
TSharedPtr<FJsonObject> ReadJsonObject(const FString& FilePath, FString& OutError)
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *FilePath))
	{
		OutError = FString::Printf(TEXT("Could not read JSON file: %s"), *FilePath);
		return nullptr;
	}

	TSharedPtr<FJsonObject> JsonObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		OutError = FString::Printf(TEXT("Invalid JSON object: %s"), *FilePath);
		return nullptr;
	}

	return JsonObject;
}

FString ToJsonText(const TSharedRef<FJsonObject>& JsonObject)
{
	FString JsonText;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
	FJsonSerializer::Serialize(JsonObject, Writer);
	return JsonText;
}

void AddError(const TSharedRef<FJsonObject>& Report, const FString& Code, const FString& Message)
{
	TArray<TSharedPtr<FJsonValue>> Errors = Report->GetArrayField(TEXT("errors"));
	const TSharedRef<FJsonObject> ErrorObject = MakeShared<FJsonObject>();
	ErrorObject->SetStringField(TEXT("code"), Code);
	ErrorObject->SetStringField(TEXT("message"), Message);
	Errors.Add(MakeShared<FJsonValueObject>(ErrorObject));
	Report->SetArrayField(TEXT("errors"), Errors);
}

bool WriteReport(const FString& ReportPath, const TSharedRef<FJsonObject>& Report)
{
	return FFileHelper::SaveStringToFile(ToJsonText(Report), *ReportPath);
}

FString DefaultReportPath(const FString& RequestPath)
{
	const FString ProjectSavedDir = FPaths::ProjectSavedDir() / TEXT("WidgetBlueprintGenerator");
	return ProjectSavedDir / (FPaths::GetBaseFilename(RequestPath) + TEXT(".report.json"));
}

bool ReadHierarchy(const FString& AssetPath, TArray<FString>& OutNames, FString& OutError)
{
	return UWidgetBlueprintGeneratorLibrary::ReadWidgetBlueprintHierarchy(AssetPath, OutNames, OutError) > 0 && OutError.IsEmpty();
}

bool RequireStringField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName, FString& OutValue, const TSharedRef<FJsonObject>& Report)
{
	if (!JsonObject->TryGetStringField(FieldName, OutValue) || OutValue.IsEmpty())
	{
		AddError(Report, TEXT("invalid_request"), FString::Printf(TEXT("Missing required string field: %s"), FieldName));
		return false;
	}

	return true;
}

bool RequireObjectField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName, TSharedPtr<FJsonObject>& OutValue, const TSharedRef<FJsonObject>& Report)
{
	const TSharedPtr<FJsonObject>* ObjectValue = nullptr;
	if (!JsonObject->TryGetObjectField(FStringView(FieldName), ObjectValue) || ObjectValue == nullptr || !ObjectValue->IsValid())
	{
		AddError(Report, TEXT("invalid_request"), FString::Printf(TEXT("Missing required object field: %s"), FieldName));
		return false;
	}

	OutValue = *ObjectValue;
	return true;
}
}

UWidgetBlueprintGeneratorCommandlet::UWidgetBlueprintGeneratorCommandlet()
{
	IsClient = false;
	IsEditor = true;
	IsServer = false;
	LogToConsole = true;
}

int32 UWidgetBlueprintGeneratorCommandlet::Main(const FString& Params)
{
	FString RequestPath;
	if (!FParse::Value(*Params, TEXT("Request="), RequestPath))
	{
		UE_LOG(LogTemp, Error, TEXT("Missing -Request=<path>."));
		return 1;
	}

	FString Error;
	const TSharedPtr<FJsonObject> Request = ReadJsonObject(RequestPath, Error);
	if (!Request.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("%s"), *Error);
		return 1;
	}

	FString ReportPath;
	if (!Request->TryGetStringField(TEXT("report_path"), ReportPath) || ReportPath.IsEmpty())
	{
		ReportPath = DefaultReportPath(RequestPath);
	}

	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	Report->SetBoolField(TEXT("ok"), false);
	Report->SetArrayField(TEXT("errors"), {});

	FString Mode;
	bool bForce = false;
	Request->TryGetBoolField(TEXT("force"), bForce);
	FString AssetPath;

	if (RequireStringField(Request.ToSharedRef(), TEXT("mode"), Mode, Report) && Mode == TEXT("generate"))
	{
		TSharedPtr<FJsonObject> Spec;
		FString ParentClassPath;
		if (!RequireObjectField(Request.ToSharedRef(), TEXT("spec"), Spec, Report)
			|| !RequireStringField(Spec.ToSharedRef(), TEXT("asset_path"), AssetPath, Report)
			|| !RequireStringField(Spec.ToSharedRef(), TEXT("parent_class"), ParentClassPath, Report))
		{
			WriteReport(ReportPath, Report);
			return 1;
		}
		const FString SpecJson = ToJsonText(Spec.ToSharedRef());

		if (!UWidgetBlueprintGeneratorLibrary::CreateWidgetBlueprint(AssetPath, ParentClassPath, bForce, Error))
		{
			AddError(Report, TEXT("create_failed"), Error);
		}
		else if (!UWidgetBlueprintGeneratorLibrary::PopulateWidgetBlueprintFromJson(AssetPath, SpecJson, Error))
		{
			AddError(Report, TEXT("populate_failed"), Error);
		}
	}
	else if (Mode == TEXT("patch"))
	{
		FString ParentWidgetName;
		TSharedPtr<FJsonObject> Widget;
		if (!RequireStringField(Request.ToSharedRef(), TEXT("asset_path"), AssetPath, Report)
			|| !RequireStringField(Request.ToSharedRef(), TEXT("parent_widget_name"), ParentWidgetName, Report)
			|| !RequireObjectField(Request.ToSharedRef(), TEXT("widget"), Widget, Report))
		{
			WriteReport(ReportPath, Report);
			return 1;
		}

		if (!UWidgetBlueprintGeneratorLibrary::AddWidgetToWidgetBlueprintFromJson(AssetPath, ParentWidgetName, ToJsonText(Widget.ToSharedRef()), Error))
		{
			AddError(Report, TEXT("patch_failed"), Error);
		}
	}
	else
	{
		AddError(Report, TEXT("invalid_mode"), FString::Printf(TEXT("Unsupported mode: %s"), *Mode));
	}

	TArray<FString> WidgetNames;
	if (!AssetPath.IsEmpty() && Report->GetArrayField(TEXT("errors")).IsEmpty())
	{
		if (!UEditorAssetLibrary::SaveAsset(AssetPath, false))
		{
			AddError(Report, TEXT("save_failed"), AssetPath);
		}
		else if (!ReadHierarchy(AssetPath, WidgetNames, Error))
		{
			AddError(Report, TEXT("verify_failed"), Error);
		}
	}

	Report->SetStringField(TEXT("asset_path"), AssetPath);
	Report->SetNumberField(TEXT("verified_widget_count"), WidgetNames.Num());
	TArray<TSharedPtr<FJsonValue>> WidgetNameValues;
	for (const FString& WidgetName : WidgetNames)
	{
		WidgetNameValues.Add(MakeShared<FJsonValueString>(WidgetName));
	}
	Report->SetArrayField(TEXT("verified_widget_names"), WidgetNameValues);
	Report->SetBoolField(TEXT("ok"), Report->GetArrayField(TEXT("errors")).IsEmpty());

	if (!WriteReport(ReportPath, Report))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to write report: %s"), *ReportPath);
		return 1;
	}

	UE_LOG(LogTemp, Display, TEXT("%s"), *ToJsonText(Report));
	return Report->GetBoolField(TEXT("ok")) ? 0 : 1;
}
